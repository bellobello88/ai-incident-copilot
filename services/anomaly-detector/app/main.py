import math
import os
from datetime import datetime, UTC
from typing import Any, Dict, List

import httpx
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel


PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")

ERROR_COUNT_THRESHOLD = float(os.getenv("ERROR_COUNT_THRESHOLD", "1"))
LATENCY_SECONDS_THRESHOLD = float(os.getenv("LATENCY_SECONDS_THRESHOLD", "1.0"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")


app = FastAPI(
    title="Anomaly Detector",
    description="Detects service anomalies using Prometheus metrics and generates incident reports.",
    version="0.1.0",
)


class Incident(BaseModel):
    type: str
    service: str
    severity: str
    value: float
    threshold: float
    message: str


class IncidentReport(BaseModel):
    service: str
    status: str
    checked_at: str
    incident_count: int
    summary: str
    root_cause_hypothesis: str
    recommended_actions: List[str]
    incidents: List[Incident]


@app.get("/health")
def health_check():
    return {
        "service": "anomaly-detector",
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
    }


async def query_prometheus(promql: str) -> List[Dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": promql},
            )
            response.raise_for_status()

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach Prometheus: {exc}",
        )

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Prometheus returned error: {exc.response.status_code}",
        )

    data = response.json()

    if data.get("status") != "success":
        raise HTTPException(
            status_code=503,
            detail="Prometheus query failed",
        )

    return data.get("data", {}).get("result", [])


def parse_value(result: Dict[str, Any]) -> float:
    raw_value = result.get("value", [None, "0"])[1]

    try:
        value = float(raw_value)
    except ValueError:
        return 0.0

    if not math.isfinite(value):
        return 0.0

    return value


async def collect_incidents() -> List[Incident]:
    incidents: List[Incident] = []

    error_query = """
    sum by (service) (
      increase(http_request_errors_total[5m])
    )
    """

    latency_query = """
    sum by (service) (
      rate(http_request_duration_seconds_sum[5m])
    )
    /
    sum by (service) (
      rate(http_request_duration_seconds_count[5m])
    )
    """

    error_results = await query_prometheus(error_query)
    latency_results = await query_prometheus(latency_query)

    for result in error_results:
        service = result.get("metric", {}).get("service", "unknown-service")
        error_count = parse_value(result)

        if error_count >= ERROR_COUNT_THRESHOLD:
            incidents.append(
                Incident(
                    type="high_error_count",
                    service=service,
                    severity="warning" if error_count < 5 else "critical",
                    value=error_count,
                    threshold=ERROR_COUNT_THRESHOLD,
                    message=f"{service} has {error_count:.0f} errors in the last 5 minutes",
                )
            )

    for result in latency_results:
        service = result.get("metric", {}).get("service", "unknown-service")
        avg_latency = parse_value(result)

        if avg_latency >= LATENCY_SECONDS_THRESHOLD:
            incidents.append(
                Incident(
                    type="high_latency",
                    service=service,
                    severity="warning" if avg_latency < 3 else "critical",
                    value=avg_latency,
                    threshold=LATENCY_SECONDS_THRESHOLD,
                    message=f"{service} average latency is {avg_latency:.2f}s in the last 5 minutes",
                )
            )

    return incidents


def generate_summary(incidents: List[Incident]) -> str:
    if not incidents:
        return "No active incidents detected. All monitored services appear healthy."

    affected_services = sorted({incident.service for incident in incidents})
    critical_count = sum(1 for incident in incidents if incident.severity == "critical")

    return (
        f"Detected {len(incidents)} active incident(s) across "
        f"{len(affected_services)} service(s): {', '.join(affected_services)}. "
        f"Critical incidents: {critical_count}."
    )


def generate_root_cause_hypothesis(incidents: List[Incident]) -> str:
    if not incidents:
        return "No anomaly pattern is currently present."

    error_services = [i.service for i in incidents if i.type == "high_error_count"]
    latency_services = [i.service for i in incidents if i.type == "high_latency"]

    if error_services and latency_services:
        overlap = set(error_services) & set(latency_services)

        if overlap:
            return (
                f"{', '.join(sorted(overlap))} is showing both elevated errors and latency. "
                "This may indicate an overloaded service, slow dependency, database issue, or recent code regression."
            )

        return (
            "Some services are failing while others are slow. "
            "This may indicate dependency failure, cascading latency, or degraded downstream communication."
        )

    if error_services:
        return (
            f"{', '.join(sorted(set(error_services)))} is showing elevated errors. "
            "Likely causes include invalid requests, dependency failures, database errors, or application exceptions."
        )

    if latency_services:
        return (
            f"{', '.join(sorted(set(latency_services)))} is showing elevated latency. "
            "Likely causes include slow database queries, service overload, network delay, or inefficient request handling."
        )

    return "Anomaly detected, but root cause pattern is unclear."


def generate_recommended_actions(incidents: List[Incident]) -> List[str]:
    if not incidents:
        return [
            "Continue monitoring service metrics.",
            "Review dashboards periodically for changes in traffic, latency, or errors.",
        ]

    actions = [
        "Open Grafana and check request rate, latency, and error panels.",
        "Check structured JSON logs for the affected service.",
        "Look for recent code changes, config changes, or container restarts.",
    ]

    incident_types = {incident.type for incident in incidents}

    if "high_error_count" in incident_types:
        actions.append("Inspect 4xx/5xx responses and identify which endpoint is failing.")

    if "high_latency" in incident_types:
        actions.append("Check slow endpoints and database query latency.")

    affected_services = sorted({incident.service for incident in incidents})
    actions.append(f"Prioritize investigation on: {', '.join(affected_services)}.")

    return actions


def build_report(incidents: List[Incident]) -> IncidentReport:
    return IncidentReport(
        service="anomaly-detector",
        status="incident_detected" if incidents else "normal",
        checked_at=datetime.now(UTC).isoformat(),
        incident_count=len(incidents),
        summary=generate_summary(incidents),
        root_cause_hypothesis=generate_root_cause_hypothesis(incidents),
        recommended_actions=generate_recommended_actions(incidents),
        incidents=incidents,
    )


def generate_llm_analysis(report: IncidentReport) -> str:
    if not OPENAI_API_KEY:
        return "LLM is disabled because OPENAI_API_KEY is not configured."

    client = OpenAI(api_key=OPENAI_API_KEY)

    incident_payload = {
        "status": report.status,
        "checked_at": report.checked_at,
        "incident_count": report.incident_count,
        "summary": report.summary,
        "root_cause_hypothesis": report.root_cause_hypothesis,
        "recommended_actions": report.recommended_actions,
        "incidents": [incident.model_dump() for incident in report.incidents],
    }

    prompt = f"""
You are an incident commander helping an SRE team.

Analyze this incident report and produce a concise operational incident analysis.

Return the answer in this format:

1. Executive Summary
2. Most Likely Root Cause
3. Impacted Services
4. Immediate Mitigation Steps
5. Follow-up Debugging Plan

Incident data:
{incident_payload}
"""

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=(
                "You are a senior SRE incident commander. "
                "Be concise, practical, and avoid claiming certainty when evidence is limited."
            ),
            input=prompt,
            max_output_tokens=700,
        )

        return response.output_text

    except Exception as exc:
        return f"LLM analysis failed. Falling back to rule-based report. Error: {type(exc).__name__}: {exc}"


@app.get("/detect")
async def detect_anomalies():
    incidents = await collect_incidents()

    return {
        "service": "anomaly-detector",
        "status": "incident_detected" if incidents else "normal",
        "checked_at": datetime.now(UTC).isoformat(),
        "incident_count": len(incidents),
        "incidents": incidents,
    }


@app.get("/report", response_model=IncidentReport)
async def generate_incident_report():
    incidents = await collect_incidents()
    return build_report(incidents)


@app.get("/report/llm")
async def generate_llm_incident_report():
    incidents = await collect_incidents()
    report = build_report(incidents)

    llm_analysis = generate_llm_analysis(report)

    return {
        "service": "anomaly-detector",
        "llm_enabled": bool(OPENAI_API_KEY),
        "llm_model": OPENAI_MODEL if OPENAI_API_KEY else None,
        "llm_analysis": llm_analysis,
        "base_report": report,
    }
