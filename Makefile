.PHONY: up down build logs ps smoke test demo report llm-report save-report clean doctor

doctor:
	docker compose config
	docker compose ps
	curl -fsS http://localhost:8001/health
	curl -fsS http://localhost:8002/health
	curl -fsS http://localhost:8003/health
	curl -fsS http://localhost:8004/health
	curl -fsS http://localhost:8005/health
	curl -fsS http://localhost:9090/-/healthy
	curl -fsS http://localhost:3000/api/health

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

ps:
	docker compose ps

smoke:
	bash scripts/smoke_test.sh

demo:
	bash scripts/demo_incident.sh

report:
	curl -s http://localhost:8004/report | python3 -m json.tool

llm-report:
	curl -s http://localhost:8004/report/llm | python3 -m json.tool

save-report:
	curl -s -X POST http://localhost:8004/report/llm/save | python3 -m json.tool

clean:
	docker compose down -v

test:
	python3 -m pytest -q
