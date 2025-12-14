# Monitoring & Alerting Setup Guide

This guide provides step-by-step instructions for deploying the production monitoring infrastructure for the AI Customer Support Agent.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Prometheus Setup](#prometheus-setup)
3. [Grafana Dashboard Import](#grafana-dashboard-import)
4. [Alert Configuration](#alert-configuration)
5. [Metrics Instrumentation](#metrics-instrumentation)
6. [Testing & Validation](#testing--validation)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Components
- **Kubernetes Cluster** (EKS, GKE, or AKS)
- **Prometheus** (v2.40+)
- **Grafana** (v8.0+)
- **Prometheus AlertManager** (v0.25+)
- **PagerDuty** account (for critical alerts)

### Required Access
- Kubernetes cluster admin privileges
- Grafana admin access
- PagerDuty API key
- AWS CloudWatch access (for cost metrics)

---

## Prometheus Setup

### 1. Deploy Prometheus Operator

Using Helm:

```bash
# Add Prometheus community Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus Operator
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=100Gi
```

### 2. Configure ServiceMonitor

Create a ServiceMonitor to scrape AI agent metrics:

```yaml
# ai-agent-servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: ai-agent-metrics
  namespace: monitoring
  labels:
    app: ai-agent
spec:
  selector:
    matchLabels:
      app: ai-agent
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
    scheme: http
```

Apply the configuration:

```bash
kubectl apply -f ai-agent-servicemonitor.yaml
```

### 3. Expose Metrics Endpoint

Ensure your AI agent application exposes Prometheus metrics on `/metrics`:

```python
# Python example using prometheus_client
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from flask import Flask, Response

app = Flask(__name__)

# Define metrics
tickets_processed = Counter(
    'ai_agent_tickets_processed_total',
    'Total tickets processed',
    ['category', 'environment']
)

response_duration = Histogram(
    'ai_agent_response_duration_milliseconds',
    'Response duration in milliseconds',
    buckets=[100, 500, 1000, 2000, 5000, 10000, 20000]
)

queue_depth = Gauge(
    'ai_agent_queue_depth',
    'Current queue depth'
)

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype='text/plain')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
```

---

## Grafana Dashboard Import

### 1. Access Grafana

Forward Grafana port to local machine:

```bash
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
```

Access Grafana at: `http://localhost:3000`

**Default credentials:**
- Username: `admin`
- Password: Retrieved via: `kubectl get secret -n monitoring prometheus-grafana -o jsonpath="{.data.admin-password}" | base64 --decode`

### 2. Configure Prometheus Data Source

1. Navigate to **Configuration**  **Data Sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Configure:
   - **Name**: Prometheus
   - **URL**: `http://prometheus-kube-prometheus-prometheus.monitoring:9090`
   - **Access**: Server (default)
5. Click **Save & Test**

### 3. Import Operations Dashboard

**Option A: Via UI**

1. Click **+** icon  **Import**
2. Upload `grafana-operations-dashboard.json`
3. Select Prometheus data source
4. Click **Import**

**Option B: Via API**

```bash
curl -X POST http://admin:password@localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana-operations-dashboard.json
```

### 4. Import Cost Dashboard

Repeat the import process with `grafana-cost-dashboard.json`

**Dashboard URLs after import:**
- Operations: `http://localhost:3000/d/ai-support-ops-001`
- Cost Monitoring: `http://localhost:3000/d/ai-support-cost-001`

---

## Alert Configuration

### 1. Deploy Alert Rules

Create PrometheusRule resource:

```bash
# Convert YAML to Kubernetes resource
kubectl create configmap prometheus-ai-agent-rules \
  --from-file=prometheus-alert-rules.yml \
  -n monitoring
```

**Or apply as PrometheusRule:**

```yaml
# prometheus-rule.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: ai-agent-alerts
  namespace: monitoring
  labels:
    prometheus: kube-prometheus
spec:
  groups:
  - name: ai_agent_critical_alerts
    interval: 30s
    rules:
    # Paste rules from prometheus-alert-rules.yml here
```

```bash
kubectl apply -f prometheus-rule.yaml
```

### 2. Configure AlertManager

Create AlertManager configuration with PagerDuty integration:

```yaml
# alertmanager-config.yaml
apiVersion: v1
kind: Secret
metadata:
  name: alertmanager-prometheus-kube-prometheus-alertmanager
  namespace: monitoring
type: Opaque
stringData:
  alertmanager.yaml: |
    global:
      resolve_timeout: 5m
      pagerduty_url: https://events.pagerduty.com/v2/enqueue
    
    route:
      group_by: ['alertname', 'severity']
      group_wait: 10s
      group_interval: 5m
      repeat_interval: 4h
      receiver: 'pagerduty-critical'
      routes:
      - match:
          severity: warning
        receiver: 'pagerduty-warning'
        continue: true
      - match:
          severity: critical
        receiver: 'pagerduty-critical'
    
    receivers:
    - name: 'pagerduty-critical'
      pagerduty_configs:
      - service_key: '<YOUR_PAGERDUTY_SERVICE_KEY>'
        severity: 'critical'
        description: '{{ .CommonAnnotations.summary }}'
        details:
          firing: '{{ .Alerts.Firing | len }}'
          resolved: '{{ .Alerts.Resolved | len }}'
          description: '{{ .CommonAnnotations.description }}'
          runbook: '{{ .CommonAnnotations.runbook }}'
    
    - name: 'pagerduty-warning'
      pagerduty_configs:
      - service_key: '<YOUR_PAGERDUTY_SERVICE_KEY>'
        severity: 'warning'
        description: '{{ .CommonAnnotations.summary }}'
```

Apply the configuration:

```bash
kubectl apply -f alertmanager-config.yaml
```

### 3. Test Alerts

Manually trigger a test alert:

```bash
# Create a temporary high error rate
kubectl exec -it <ai-agent-pod> -- /bin/bash -c "
  for i in {1..100}; do
    curl -X POST http://localhost:8000/api/test/error
  done
"
```

Verify alert fires in Prometheus:
- Navigate to `http://localhost:9090/alerts`
- Look for `HighErrorRate` alert

---

## Metrics Instrumentation

### Required Metrics

Your application must expose these Prometheus metrics:

#### Counter Metrics
```python
from prometheus_client import Counter

ai_agent_tickets_processed_total = Counter(
    'ai_agent_tickets_processed_total',
    'Total tickets processed',
    ['category', 'environment']
)

ai_agent_tickets_resolved_auto_total = Counter(
    'ai_agent_tickets_resolved_auto_total',
    'Tickets resolved automatically by AI',
    ['category']
)

ai_agent_tickets_escalated_total = Counter(
    'ai_agent_tickets_escalated_total',
    'Tickets escalated to human agents',
    ['category', 'reason']
)

ai_agent_http_requests_total = Counter(
    'ai_agent_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

ai_agent_llm_api_requests_total = Counter(
    'ai_agent_llm_api_requests_total',
    'Total LLM API requests',
    ['provider', 'model']
)

ai_agent_llm_tokens_total = Counter(
    'ai_agent_llm_tokens_total',
    'Total LLM tokens consumed',
    ['provider', 'model', 'type']  # type: input or output
)

ai_agent_llm_api_cost_dollars = Counter(
    'ai_agent_llm_api_cost_dollars',
    'Cumulative LLM API cost in USD',
    ['provider', 'model']
)
```

#### Histogram Metrics
```python
from prometheus_client import Histogram

ai_agent_response_duration_milliseconds = Histogram(
    'ai_agent_response_duration_milliseconds',
    'Response duration in milliseconds',
    buckets=[100, 500, 1000, 2000, 5000, 10000, 20000, 30000]
)

ai_agent_llm_response_duration_seconds = Histogram(
    'ai_agent_llm_response_duration_seconds',
    'LLM response duration in seconds',
    buckets=[0.5, 1, 2, 5, 10, 15, 30, 60]
)
```

#### Gauge Metrics
```python
from prometheus_client import Gauge

ai_agent_queue_depth = Gauge(
    'ai_agent_queue_depth',
    'Current queue depth'
)

ai_agent_db_connections_active = Gauge(
    'ai_agent_db_connections_active',
    'Active database connections'
)

ai_agent_db_connections_max = Gauge(
    'ai_agent_db_connections_max',
    'Maximum database connections'
)

ai_agent_customer_satisfaction_score = Gauge(
    'ai_agent_customer_satisfaction_score',
    'Current CSAT score (0-100)'
)
```

### Example Instrumentation

```python
import time
from prometheus_client import Counter, Histogram
from functools import wraps

# Decorator for timing functions
def track_duration(histogram):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = (time.time() - start) * 1000  # Convert to ms
                histogram.observe(duration)
        return wrapper
    return decorator

# Usage example
@track_duration(ai_agent_response_duration_milliseconds)
async def process_ticket(ticket):
    # Process ticket logic
    category = classify_ticket(ticket)
    
    # Increment processed counter
    ai_agent_tickets_processed_total.labels(
        category=category,
        environment='production'
    ).inc()
    
    # Generate response
    response = await generate_response(ticket)
    
    if response.confidence > 0.75:
        ai_agent_tickets_resolved_auto_total.labels(
            category=category
        ).inc()
    else:
        ai_agent_tickets_escalated_total.labels(
            category=category,
            reason='low_confidence'
        ).inc()
    
    return response
```

---

## Testing & Validation

### 1. Verify Metrics Collection

Check if Prometheus is scraping metrics:

```bash
# Port-forward Prometheus
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

# Query a metric
curl "http://localhost:9090/api/v1/query?query=ai_agent_tickets_processed_total"
```

### 2. Validate Dashboards

Access each dashboard and verify:

**Operations Dashboard:**
- [ ] All panels load without errors
- [ ] Metrics show realistic data
- [ ] Time range selector works
- [ ] Auto-refresh is enabled (10s)

**Cost Dashboard:**
- [ ] Cost metrics are populated
- [ ] Budget tracking shows percentages
- [ ] ROI calculations are correct

### 3. Test Alert Rules

```bash
# Check if alert rules are loaded
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

# Visit http://localhost:9090/rules
# Verify all alert groups are present
```

### 4. Simulate Alert Conditions

**Test High Error Rate Alert:**

```bash
# Increase error rate temporarily
kubectl exec -it <pod-name> -- curl -X POST http://localhost:8000/test/errors?count=100
```

**Test High Queue Depth:**

```bash
# Pause ticket processing
kubectl exec -it <pod-name> -- curl -X POST http://localhost:8000/test/pause-processing

# Submit multiple tickets
for i in {1..600}; do
  curl -X POST http://localhost:8000/api/v1/tickets -d '{"subject":"Test"}'
done

# Resume processing
kubectl exec -it <pod-name> -- curl -X POST http://localhost:8000/test/resume-processing
```

---

## Troubleshooting

### Common Issues

#### Dashboards Not Showing Data

**Symptom:** All panels show "No Data"

**Solutions:**
1. Verify Prometheus data source configuration
2. Check if metrics are being scraped:
   ```bash
   # View Prometheus targets
   kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
   # Navigate to http://localhost:9090/targets
   ```
3. Ensure ServiceMonitor is created and labels match

#### Alerts Not Firing

**Symptom:** Known issues don't trigger alerts

**Solutions:**
1. Check alert rule syntax:
   ```bash
   promtool check rules prometheus-alert-rules.yml
   ```
2. Verify AlertManager is running:
   ```bash
   kubectl get pods -n monitoring | grep alertmanager
   ```
3. Check AlertManager logs:
   ```bash
   kubectl logs -n monitoring alertmanager-prometheus-kube-prometheus-alertmanager-0
   ```

#### High Memory Usage

**Symptom:** Prometheus pod OOMKilled

**Solutions:**
1. Reduce retention period:
   ```bash
   helm upgrade prometheus prometheus-community/kube-prometheus-stack \
     --set prometheus.prometheusSpec.retention=15d
   ```
2. Increase memory limits:
   ```yaml
   prometheus:
     prometheusSpec:
       resources:
         requests:
           memory: 4Gi
         limits:
           memory: 8Gi
   ```

#### Missing Cost Metrics

**Symptom:** Cost dashboard shows no data

**Solutions:**
1. Implement AWS Cost Explorer integration:
   ```python
   import boto3
   from prometheus_client import Gauge
   
   cost_gauge = Gauge('ai_agent_aws_infrastructure_cost_dollars', 
                      'AWS infrastructure costs')
   
   def update_aws_costs():
       ce = boto3.client('ce', region_name='us-east-1')
       response = ce.get_cost_and_usage(
           TimePeriod={
               'Start': '2024-01-01',
               'End': '2024-01-31'
           },
           Granularity='MONTHLY',
           Metrics=['UnblendedCost']
       )
       cost = float(response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
       cost_gauge.set(cost)
   ```

---

## Production Checklist

Before going live, verify:

- [ ] All dashboards imported successfully
- [ ] Prometheus scraping all targets (check `/targets`)
- [ ] Alert rules loaded and valid
- [ ] AlertManager routing configured
- [ ] PagerDuty integration tested
- [ ] Metric retention set appropriately (30 days)
- [ ] Grafana authentication configured
- [ ] Dashboard permissions set
- [ ] SSL/TLS enabled for external access
- [ ] Backup strategy implemented for Prometheus data
- [ ] High availability configured (3+ Prometheus replicas)
- [ ] Runbooks created for each alert
- [ ] Team trained on dashboard interpretation

---

## Maintenance

### Regular Tasks

**Daily:**
- Monitor alert volume in PagerDuty
- Check for dashboard loading issues

**Weekly:**
- Review alert thresholds for accuracy
- Analyze cost trends
- Update runbooks based on incidents

**Monthly:**
- Prune old Prometheus data
- Review and optimize slow queries
- Update dashboard layouts based on team feedback
- Audit PagerDuty escalation policies

---

## Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [AlertManager Configuration](https://prometheus.io/docs/alerting/latest/configuration/)
- [PromQL Tutorial](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)

---

## Support

For issues or questions:
- **GitHub Issues**: https://github.com/eliasdphiri/ai-support-agent.git
- **Team Slack**: #ai-agent-monitoring

---

**Last Updated:** December 2025
**Document Version:** 1.0
