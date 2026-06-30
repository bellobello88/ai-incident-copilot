#!/usr/bin/env bash

set -euo pipefail

check_url() {
  local name="$1"
  local url="$2"
  local max_attempts="${3:-60}"
  local sleep_seconds="${4:-2}"

  echo "Checking ${name}: ${url}"

  for attempt in $(seq 1 "$max_attempts"); do
    if curl -fsS "$url" > /tmp/"${name}".out 2>/tmp/"${name}".err; then
      echo "✅ ${name} is healthy"
      return 0
    fi

    echo "Attempt ${attempt}/${max_attempts} failed for ${name}. Retrying in ${sleep_seconds}s..."
    sleep "$sleep_seconds"
  done

  echo "❌ ${name} failed health check"
  echo "Last stderr:"
  cat /tmp/"${name}".err || true
  docker compose ps
  exit 1
}

check_url "order-service" "http://localhost:8001/health"
check_url "user-service" "http://localhost:8002/health"
check_url "inventory-service" "http://localhost:8003/health"
check_url "anomaly-detector" "http://localhost:8004/health"
check_url "traffic-generator" "http://localhost:8005/health"

check_url "prometheus" "http://localhost:9090/-/healthy"
check_url "grafana" "http://localhost:3000/api/health"
check_url "jaeger" "http://localhost:16686"
check_url "incident-dashboard" "http://localhost:8501"

echo "Generating normal traffic..."
curl -fsS -X POST "http://localhost:8005/generate/normal?requests_per_service=1" > /tmp/traffic_normal.json

echo "Checking anomaly detector report..."
check_url "anomaly-report" "http://localhost:8004/report"

echo "Checking LLM report fallback..."
check_url "llm-report" "http://localhost:8004/report/llm"

echo "✅ All smoke tests passed"
