# AI Incident Copilot

An AI-powered observability platform for microservices incident detection and root cause analysis.

## Goal

This project simulates a small microservices system and adds observability features such as logs, metrics, tracing, anomaly detection, and AI-generated incident summaries.

## Week 1 Goal

Build the basic microservices foundation.

- Set up GitHub repo
- Create project folder structure
- Add Docker Compose
- Prepare three services:
  - order-service
  - payment-service
  - inventory-service
- Add PostgreSQL

## Architecture Draft

order-service → payment-service  
order-service → inventory-service  
services → PostgreSQL

## How to Run

```bash
docker compose up