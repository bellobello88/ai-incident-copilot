#!/usr/bin/env bash

set -euo pipefail

echo "🚨 AI Incident Copilot Demo"
echo "=========================="

echo ""
echo "1. Checking traffic-generator health..."
curl -fsS http://localhost:8005/health | python3 -m json.tool

echo ""
echo "2. Generating normal traffic..."
curl -fsS -X POST "http://localhost:8005/generate/normal?requests_per_service=3" | python3 -m json.tool

echo ""
echo "3. Generating mixed incident traffic..."
curl -fsS -X POST "http://localhost:8005/generate/mixed" | python3 -m json.tool

echo ""
echo "4. Waiting for Prometheus to scrape metrics..."
sleep 10

echo ""
echo "5. Fetching incident report..."
curl -fsS http://localhost:8004/report | python3 -m json.tool

echo ""
echo "6. Fetching LLM incident report or fallback..."
curl -fsS http://localhost:8004/report/llm | python3 -m json.tool

echo ""
echo "7. Saving incident snapshot..."
curl -fsS -X POST http://localhost:8004/report/llm/save | python3 -m json.tool

echo ""
echo "✅ Demo complete"
echo ""
echo "Open these dashboards:"
echo "- Streamlit:   http://localhost:8501"
echo "- Grafana:     http://localhost:3000"
echo "- Prometheus:  http://localhost:9090"
echo "- Jaeger:      http://localhost:16686"
