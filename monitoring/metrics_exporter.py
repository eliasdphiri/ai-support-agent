"""
AI Agent Prometheus Metrics Exporter
=====================================

This module implements comprehensive Prometheus metrics instrumentation for the
AI Customer Support Agent, tracking performance, costs, quality, and operational metrics.

Usage:
    from metrics_exporter import metrics, track_ticket_processing
    
    @track_ticket_processing
    async def process_ticket(ticket):
        # Your processing logic
        pass
"""

import time
import logging
from functools import wraps
from typing import Optional, Callable, Any
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    generate_latest,
    REGISTRY
)
from flask import Flask, Response

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# COUNTER METRICS
# ============================================================================

# Ticket Processing Metrics
tickets_processed_total = Counter(
    'ai_agent_tickets_processed_total',
    'Total number of tickets processed',
    ['category', 'environment', 'channel']
)

tickets_resolved_auto_total = Counter(
    'ai_agent_tickets_resolved_auto_total',
    'Tickets resolved automatically without human intervention',
    ['category', 'confidence_tier']  # confidence_tier: high, medium, low
)

tickets_escalated_total = Counter(
    'ai_agent_tickets_escalated_total',
    'Tickets escalated to human agents',
    ['category', 'escalation_reason']
)

# HTTP API Metrics
http_requests_total = Counter(
    'ai_agent_http_requests_total',
    'Total HTTP requests received',
    ['method', 'endpoint', 'status']
)

# LLM API Metrics
llm_api_requests_total = Counter(
    'ai_agent_llm_api_requests_total',
    'Total LLM API requests made',
    ['provider', 'model', 'status']
)

llm_api_errors_total = Counter(
    'ai_agent_llm_api_errors_total',
    'Total LLM API errors',
    ['provider', 'error_type']
)

llm_tokens_total = Counter(
    'ai_agent_llm_tokens_total',
    'Total tokens consumed',
    ['provider', 'model', 'token_type']  # token_type: input, output
)

# Cost Metrics
llm_api_cost_dollars = Counter(
    'ai_agent_llm_api_cost_dollars',
    'Cumulative LLM API costs in USD',
    ['provider', 'model']
)

aws_compute_cost_dollars = Counter(
    'ai_agent_aws_compute_cost_dollars',
    'AWS compute costs (EKS)',
    ['resource_type']
)

aws_database_cost_dollars = Counter(
    'ai_agent_aws_database_cost_dollars',
    'AWS database costs (RDS, ElastiCache)',
    ['service']
)

vector_db_cost_dollars = Counter(
    'ai_agent_vector_db_cost_dollars',
    'Vector database costs (Pinecone)',
    []
)

monitoring_cost_dollars = Counter(
    'ai_agent_monitoring_cost_dollars',
    'Monitoring and observability costs',
    ['tool']
)

total_monthly_cost_dollars = Counter(
    'ai_agent_total_monthly_cost_dollars',
    'Total monthly operational costs',
    []
)

aws_infrastructure_cost_dollars = Counter(
    'ai_agent_aws_infrastructure_cost_dollars',
    'Total AWS infrastructure costs',
    []
)


# ============================================================================
# HISTOGRAM METRICS
# ============================================================================

# Response Time Metrics
response_duration_milliseconds = Histogram(
    'ai_agent_response_duration_milliseconds',
    'End-to-end ticket response duration in milliseconds',
    buckets=[100, 250, 500, 1000, 2000, 3000, 5000, 10000, 15000, 20000, 30000]
)

llm_response_duration_seconds = Histogram(
    'ai_agent_llm_response_duration_seconds',
    'LLM API response time in seconds',
    ['provider', 'model'],
    buckets=[0.5, 1, 2, 3, 5, 10, 15, 20, 30, 60]
)

vector_search_duration_milliseconds = Histogram(
    'ai_agent_vector_search_duration_milliseconds',
    'Vector similarity search duration',
    buckets=[10, 25, 50, 100, 250, 500, 1000]
)

database_query_duration_milliseconds = Histogram(
    'ai_agent_database_query_duration_milliseconds',
    'Database query duration',
    ['query_type'],
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000]
)


# ============================================================================
# GAUGE METRICS
# ============================================================================

# Queue Metrics
queue_depth = Gauge(
    'ai_agent_queue_depth',
    'Current number of tickets in processing queue',
    ['priority']
)

# Database Connection Pool
db_connections_active = Gauge(
    'ai_agent_db_connections_active',
    'Currently active database connections'
)

db_connections_max = Gauge(
    'ai_agent_db_connections_max',
    'Maximum allowed database connections'
)

db_connections_idle = Gauge(
    'ai_agent_db_connections_idle',
    'Currently idle database connections'
)

# Quality Metrics
customer_satisfaction_score = Gauge(
    'ai_agent_customer_satisfaction_score',
    'Current CSAT score (0-100)',
    []
)

ai_confidence_score = Gauge(
    'ai_agent_confidence_score',
    'Average AI confidence score for recent responses',
    ['category']
)

# Cost Budget Tracking
cost_budget_monthly = Gauge(
    'ai_agent_cost_budget_monthly',
    'Monthly cost budget by category',
    ['category']
)

# Savings Metrics
support_agent_cost_savings_dollars = Gauge(
    'ai_agent_support_agent_cost_savings_dollars',
    'Monthly savings from reduced support staffing needs',
    []
)

monthly_cost_savings_dollars = Gauge(
    'ai_agent_monthly_cost_savings_dollars',
    'Net monthly cost savings (revenue - costs)',
    []
)

# Deployment Info
deployment_version = Info(
    'ai_agent_deployment_version',
    'Current deployment version and metadata'
)


# ============================================================================
# DECORATOR FUNCTIONS FOR AUTOMATIC INSTRUMENTATION
# ============================================================================

def track_ticket_processing(func: Callable) -> Callable:
    """
    Decorator to automatically track ticket processing metrics.
    
    Usage:
        @track_ticket_processing
        async def process_ticket(ticket):
            # Your logic here
            return response
    """
    @wraps(func)
    async def wrapper(ticket, *args, **kwargs):
        start_time = time.time()
        category = ticket.get('category', 'general_inquiry')
        channel = ticket.get('channel', 'web')
        environment = kwargs.get('environment', 'production')
        
        try:
            # Process ticket
            result = await func(ticket, *args, **kwargs)
            
            # Track processing time
            duration_ms = (time.time() - start_time) * 1000
            response_duration_milliseconds.observe(duration_ms)
            
            # Track successful processing
            tickets_processed_total.labels(
                category=category,
                environment=environment,
                channel=channel
            ).inc()
            
            # Track resolution type
            if result.get('auto_resolved', False):
                confidence = result.get('confidence', 0)
                confidence_tier = 'high' if confidence > 0.85 else 'medium' if confidence > 0.70 else 'low'
                
                tickets_resolved_auto_total.labels(
                    category=category,
                    confidence_tier=confidence_tier
                ).inc()
            elif result.get('escalated', False):
                tickets_escalated_total.labels(
                    category=category,
                    escalation_reason=result.get('escalation_reason', 'unknown')
                ).inc()
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing ticket: {e}")
            raise
    
    return wrapper


def track_llm_call(provider: str, model: str):
    """
    Decorator to track LLM API calls.
    
    Usage:
        @track_llm_call(provider='anthropic', model='claude-sonnet-4')
        async def call_llm(prompt):
            # LLM API call
            return response
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                # Make LLM call
                result = await func(*args, **kwargs)
                
                # Track timing
                duration_s = time.time() - start_time
                llm_response_duration_seconds.labels(
                    provider=provider,
                    model=model
                ).observe(duration_s)
                
                # Track tokens
                if 'usage' in result:
                    input_tokens = result['usage'].get('input_tokens', 0)
                    output_tokens = result['usage'].get('output_tokens', 0)
                    
                    llm_tokens_total.labels(
                        provider=provider,
                        model=model,
                        token_type='input'
                    ).inc(input_tokens)
                    
                    llm_tokens_total.labels(
                        provider=provider,
                        model=model,
                        token_type='output'
                    ).inc(output_tokens)
                    
                    # Calculate and track cost
                    cost = calculate_llm_cost(provider, model, input_tokens, output_tokens)
                    llm_api_cost_dollars.labels(
                        provider=provider,
                        model=model
                    ).inc(cost)
                
                # Track success
                llm_api_requests_total.labels(
                    provider=provider,
                    model=model,
                    status='success'
                ).inc()
                
                return result
                
            except Exception as e:
                # Track error
                llm_api_requests_total.labels(
                    provider=provider,
                    model=model,
                    status='error'
                ).inc()
                
                llm_api_errors_total.labels(
                    provider=provider,
                    error_type=type(e).__name__
                ).inc()
                
                logger.error(f"LLM API error: {e}")
                raise
        
        return wrapper
    return decorator


def track_http_request(func: Callable) -> Callable:
    """
    Decorator to track HTTP requests.
    
    Usage:
        @track_http_request
        async def handle_request(request):
            # Handle request
            return response
    """
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        try:
            response = await func(request, *args, **kwargs)
            
            http_requests_total.labels(
                method=request.method,
                endpoint=request.path,
                status=response.status_code
            ).inc()
            
            return response
            
        except Exception as e:
            http_requests_total.labels(
                method=request.method,
                endpoint=request.path,
                status=500
            ).inc()
            raise
    
    return wrapper


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_llm_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate LLM API cost based on token usage.
    
    Pricing (as of Dec 2024):
    - Claude Sonnet 4: $3/MTok input, $15/MTok output
    - GPT-4: $30/MTok input, $60/MTok output
    """
    pricing = {
        'anthropic': {
            'claude-sonnet-4': {'input': 3.0 / 1_000_000, 'output': 15.0 / 1_000_000},
            'claude-haiku': {'input': 0.25 / 1_000_000, 'output': 1.25 / 1_000_000}
        },
        'openai': {
            'gpt-4': {'input': 30.0 / 1_000_000, 'output': 60.0 / 1_000_000},
            'gpt-3.5-turbo': {'input': 0.5 / 1_000_000, 'output': 1.5 / 1_000_000}
        }
    }
    
    if provider not in pricing or model not in pricing[provider]:
        logger.warning(f"Unknown pricing for {provider}/{model}, using default")
        return 0.0
    
    rates = pricing[provider][model]
    cost = (input_tokens * rates['input']) + (output_tokens * rates['output'])
    return cost


def update_queue_metrics(redis_client):
    """
    Update queue depth metrics from Redis.
    Should be called periodically (e.g., every 30 seconds).
    """
    try:
        # Get queue sizes for different priorities
        high_priority = redis_client.llen('queue:high')
        medium_priority = redis_client.llen('queue:medium')
        low_priority = redis_client.llen('queue:low')
        
        queue_depth.labels(priority='high').set(high_priority)
        queue_depth.labels(priority='medium').set(medium_priority)
        queue_depth.labels(priority='low').set(low_priority)
        
    except Exception as e:
        logger.error(f"Error updating queue metrics: {e}")


def update_db_connection_metrics(db_pool):
    """
    Update database connection pool metrics.
    Should be called periodically.
    """
    try:
        db_connections_active.set(db_pool.size - db_pool.free_count)
        db_connections_max.set(db_pool.max_size)
        db_connections_idle.set(db_pool.free_count)
    except Exception as e:
        logger.error(f"Error updating DB metrics: {e}")


def update_cost_budget_tracking():
    """
    Update monthly budget tracking gauges.
    Should be called daily.
    """
    budgets = {
        'llm_api': 1200,
        'aws_infrastructure': 800,
        'vector_db': 300,
        'monitoring': 200
    }
    
    for category, amount in budgets.items():
        cost_budget_monthly.labels(category=category).set(amount)
    
    # Calculate savings
    monthly_operational_cost = 2500  # Total monthly cost
    monthly_support_savings = 4000   # Savings from reduced staffing
    
    support_agent_cost_savings_dollars.set(monthly_support_savings)
    monthly_cost_savings_dollars.set(monthly_support_savings - monthly_operational_cost)


def set_deployment_info(version: str, commit_sha: str, deployed_at: str):
    """
    Set deployment metadata.
    Should be called on application startup.
    """
    deployment_version.info({
        'version': version,
        'commit_sha': commit_sha,
        'deployed_at': deployed_at,
        'python_version': '3.11'
    })


# ============================================================================
# FLASK APP FOR METRICS ENDPOINT
# ============================================================================

app = Flask(__name__)

@app.route('/metrics')
def metrics():
    """
    Prometheus metrics endpoint.
    Returns all registered metrics in Prometheus format.
    """
    return Response(generate_latest(REGISTRY), mimetype='text/plain')


@app.route('/health')
def health():
    """
    Health check endpoint.
    """
    return {'status': 'healthy', 'version': '2.4.1'}, 200


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == '__main__':
    """
    Example usage of the metrics exporter.
    """
    import asyncio
    
    # Set deployment info
    set_deployment_info(
        version='2.4.1',
        commit_sha='abc123def456',
        deployed_at='2024-12-13T10:30:00Z'
    )
    
    # Example: Process a ticket
    @track_ticket_processing
    async def process_ticket(ticket):
        # Simulate processing
        await asyncio.sleep(1.5)
        
        return {
            'auto_resolved': True,
            'confidence': 0.87,
            'response': 'Your issue has been resolved.'
        }
    
    # Example: Call LLM
    @track_llm_call(provider='anthropic', model='claude-sonnet-4')
    async def call_claude(prompt):
        # Simulate API call
        await asyncio.sleep(2.0)
        
        return {
            'response': 'Here is the answer...',
            'usage': {
                'input_tokens': 150,
                'output_tokens': 300
            }
        }
    
    async def main():
        # Process example ticket
        ticket = {
            'category': 'technical_support',
            'channel': 'email',
            'subject': 'Login issue'
        }
        
        result = await process_ticket(ticket)
        print(f"Ticket processed: {result}")
        
        # Make LLM call
        llm_result = await call_claude("How do I reset my password?")
        print(f"LLM response: {llm_result}")
        
        # Update periodic metrics
        print("Updating periodic metrics...")
        update_cost_budget_tracking()
    
    # Run example
    asyncio.run(main())
    
    # Start metrics server
    print("Starting metrics server on port 8000...")
    print("Access metrics at: http://localhost:8000/metrics")
    app.run(host='0.0.0.0', port=8000)
