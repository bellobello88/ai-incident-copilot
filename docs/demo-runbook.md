# AI Incident Copilot Demo Runbook

## Goal

This demo shows how AI Incident Copilot detects service errors and latency, generates an incident report, and saves an incident snapshot.

## System Components

- order-service: handles order APIs
- user-service: handles user APIs
- inventory-service: handles item APIs
- traffic-generator: creates normal/error/slow demo traffic
- prometheus: scrapes service metrics
- grafana: visualizes metrics
- jaeger: visualizes distributed traces
- anomaly-detector: detects incidents and generates reports
- incident-dashboard: Streamlit copilot UI
- postgres: stores application data and incident history

## Start the System

```bash
make up
```
