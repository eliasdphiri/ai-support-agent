"""
Database Initialization Script
===============================

This script initializes the PostgreSQL database schema for the AI Customer Support Agent.
It creates all necessary tables, indexes, and initial data.

Usage:
    python scripts/init_db.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ai_agent:your_password@localhost:5432/ai_support_db")

# Database schema
SCHEMA_SQL = """
-- ============================================================================
-- TABLES
-- ============================================================================

-- Tickets table
CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    ticket_id VARCHAR(50) UNIQUE NOT NULL,
    customer_id VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    priority VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(20) DEFAULT 'open',
    channel VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    assigned_to VARCHAR(100),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Ticket responses table
CREATE TABLE IF NOT EXISTS ticket_responses (
    id SERIAL PRIMARY KEY,
    ticket_id VARCHAR(50) NOT NULL,
    response_text TEXT NOT NULL,
    response_type VARCHAR(20) NOT NULL, -- 'ai' or 'human'
    confidence_score FLOAT,
    tokens_used INTEGER,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb,
    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
);

-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    phone VARCHAR(50),
    tier VARCHAR(20) DEFAULT 'standard',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_interaction TIMESTAMP,
    total_tickets INTEGER DEFAULT 0,
    satisfaction_score FLOAT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Knowledge base table
CREATE TABLE IF NOT EXISTS knowledge_base (
    id SERIAL PRIMARY KEY,
    article_id VARCHAR(50) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50),
    tags TEXT[],
    embedding_id VARCHAR(100), -- Reference to Pinecone vector
    view_count INTEGER DEFAULT 0,
    helpful_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Escalations table
CREATE TABLE IF NOT EXISTS escalations (
    id SERIAL PRIMARY KEY,
    ticket_id VARCHAR(50) NOT NULL,
    escalation_reason VARCHAR(100) NOT NULL,
    escalated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    escalated_to VARCHAR(100),
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
);

-- Metrics table (for time-series data)
CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    labels JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API costs table
CREATE TABLE IF NOT EXISTS api_costs (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd FLOAT NOT NULL,
    request_id VARCHAR(100),
    ticket_id VARCHAR(50),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User feedback table
CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    ticket_id VARCHAR(50) NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Tickets indexes
CREATE INDEX IF NOT EXISTS idx_tickets_customer_id ON tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_tickets_metadata ON tickets USING gin(metadata);

-- Ticket responses indexes
CREATE INDEX IF NOT EXISTS idx_responses_ticket_id ON ticket_responses(ticket_id);
CREATE INDEX IF NOT EXISTS idx_responses_type ON ticket_responses(response_type);
CREATE INDEX IF NOT EXISTS idx_responses_created_at ON ticket_responses(created_at);

-- Customers indexes
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_tier ON customers(tier);
CREATE INDEX IF NOT EXISTS idx_customers_metadata ON customers USING gin(metadata);

-- Knowledge base indexes
CREATE INDEX IF NOT EXISTS idx_kb_category ON knowledge_base(category);
CREATE INDEX IF NOT EXISTS idx_kb_tags ON knowledge_base USING gin(tags);
CREATE INDEX IF NOT EXISTS idx_kb_active ON knowledge_base(is_active);

-- Metrics indexes
CREATE INDEX IF NOT EXISTS idx_metrics_name_timestamp ON metrics(metric_name, timestamp);
CREATE INDEX IF NOT EXISTS idx_metrics_labels ON metrics USING gin(labels);

-- API costs indexes
CREATE INDEX IF NOT EXISTS idx_costs_provider_timestamp ON api_costs(provider, timestamp);
CREATE INDEX IF NOT EXISTS idx_costs_ticket_id ON api_costs(ticket_id);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Active tickets view
CREATE OR REPLACE VIEW active_tickets AS
SELECT 
    t.*,
    c.email as customer_email,
    c.name as customer_name,
    c.tier as customer_tier
FROM tickets t
LEFT JOIN customers c ON t.customer_id = c.customer_id
WHERE t.status IN ('open', 'in_progress');

-- Daily metrics view
CREATE OR REPLACE VIEW daily_metrics AS
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_tickets,
    COUNT(*) FILTER (WHERE status = 'resolved') as resolved_tickets,
    COUNT(*) FILTER (WHERE category = 'technical_support') as technical_tickets,
    COUNT(*) FILTER (WHERE category = 'billing_inquiry') as billing_tickets,
    AVG(CASE WHEN resolved_at IS NOT NULL 
        THEN EXTRACT(EPOCH FROM (resolved_at - created_at))/60 
        ELSE NULL END) as avg_resolution_time_minutes
FROM tickets
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Cost summary view
CREATE OR REPLACE VIEW cost_summary AS
SELECT 
    DATE(timestamp) as date,
    provider,
    model,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(cost_usd) as total_cost_usd,
    COUNT(*) as request_count
FROM api_costs
GROUP BY DATE(timestamp), provider, model
ORDER BY date DESC, total_cost_usd DESC;

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to update ticket updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for tickets table
DROP TRIGGER IF EXISTS update_tickets_updated_at ON tickets;
CREATE TRIGGER update_tickets_updated_at 
    BEFORE UPDATE ON tickets 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for knowledge_base table
DROP TRIGGER IF EXISTS update_kb_updated_at ON knowledge_base;
CREATE TRIGGER update_kb_updated_at 
    BEFORE UPDATE ON knowledge_base 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Function to calculate customer satisfaction
CREATE OR REPLACE FUNCTION calculate_customer_satisfaction(cust_id VARCHAR)
RETURNS FLOAT AS $$
DECLARE
    avg_rating FLOAT;
BEGIN
    SELECT AVG(rating)::FLOAT INTO avg_rating
    FROM user_feedback uf
    JOIN tickets t ON uf.ticket_id = t.ticket_id
    WHERE t.customer_id = cust_id;
    
    RETURN COALESCE(avg_rating * 20, 0); -- Convert 1-5 scale to 0-100
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert sample categories
INSERT INTO knowledge_base (article_id, title, content, category, tags, is_active)
VALUES 
    ('kb-001', 'Password Reset Instructions', 
     'To reset your password: 1) Go to login page, 2) Click "Forgot Password", 3) Check your email for reset link, 4) Create new password',
     'account_management', ARRAY['password', 'login', 'security'], true),
    
    ('kb-002', 'Billing Cycle Information', 
     'Your billing cycle begins on the day you sign up and repeats monthly. View your billing date in Account Settings > Billing.',
     'billing_inquiry', ARRAY['billing', 'payment', 'subscription'], true),
    
    ('kb-003', 'How to Contact Support', 
     'You can reach our support team via: Email (support@example.com), Live Chat (Mon-Fri 9am-5pm EST), or Phone (1-800-SUPPORT)',
     'general_inquiry', ARRAY['contact', 'support', 'help'], true)
ON CONFLICT (article_id) DO NOTHING;

-- Print success message
DO $$
BEGIN
    RAISE NOTICE 'Database schema initialized successfully!';
    RAISE NOTICE 'Total tables created: %', (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public');
END $$;
"""


def init_database():
    """Initialize the database schema"""
    print("=" * 80)
    print("AI Customer Support Agent - Database Initialization")
    print("=" * 80)
    print(f"\nConnecting to database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")
    
    try:
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✓ Connected to PostgreSQL: {version.split(',')[0]}\n")
        
        # Execute schema
        print("Creating database schema...")
        with engine.connect() as conn:
            # Split and execute statements
            statements = [s.strip() for s in SCHEMA_SQL.split(';') if s.strip()]
            
            for i, statement in enumerate(statements, 1):
                if statement:
                    try:
                        conn.execute(text(statement))
                        conn.commit()
                    except Exception as e:
                        print(f"  Warning on statement {i}: {str(e)[:100]}")
        
        # Verify tables
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            ))
            tables = [row[0] for row in result]
            
            print(f"\n✓ Database initialized successfully!")
            print(f"\nCreated tables ({len(tables)}):")
            for table in sorted(tables):
                print(f"  - {table}")
        
        print("\n" + "=" * 80)
        print("Database is ready for use!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ Error initializing database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    init_database()
