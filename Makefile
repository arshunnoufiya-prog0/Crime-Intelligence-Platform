.DEFAULT_GOAL := help

-include .env
export

COMPOSE ?= docker compose
PROFILES ?= --profile rerank

.PHONY: help config build up down restart ps logs fetch-models constraints migrate seed ingest test measure

help:
	@echo "ksp-iis (spec ksp-iis-build-prompt-v3.1)"
	@echo "  make fetch-models   download Qwen3.5-4B Q8_0 + bge-m3 + bge-reranker into ./models (once; §16)"
	@echo "  make config         validate compose files (Step 3 gate)"
	@echo "  make build          build all images"
	@echo "  make up             start the stack (with rerank profile)"
	@echo "  make up PROFILES='' start without the reranker (ENABLE_RERANK=false path, §8)"
	@echo "  make down | restart | ps | logs"
	@echo "  make constraints    apply Neo4j constraints (Step 4 gate)"
	@echo "  make migrate        Django migrations"
	@echo "  make seed           create default users"
	@echo "  make ingest         Neo4j load + LightRAG custom-KG ingest (Steps 6+8)"
	@echo "  make test           run local stdlib test gates"
	@echo "  make measure        perf gate (Step 16)"

config:
	$(COMPOSE) config -q
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml config -q

build:
	$(COMPOSE) $(PROFILES) build

up:
	$(COMPOSE) $(PROFILES) up -d

down:
	$(COMPOSE) $(PROFILES) down

restart:
	$(COMPOSE) $(PROFILES) restart

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

fetch-models:
	huggingface-cli download bartowski/Qwen_Qwen3.5-4B-GGUF \
	  --include "Qwen_Qwen3.5-4B-Q8_0.gguf" --local-dir ./models
	huggingface-cli download gpustack/bge-m3-GGUF \
	  --include "bge-m3-Q8_0.gguf" --local-dir ./models
	huggingface-cli download gpustack/bge-reranker-v2-m3-GGUF \
	  --include "bge-reranker-v2-m3-Q8_0.gguf" --local-dir ./models
	@ls -la models/

constraints:
	$(COMPOSE) exec neo4j cypher-shell -u neo4j -p "$$NEO4J_PASSWORD" -f /constraints/constraints.cypher

migrate:
	$(COMPOSE) exec backend python manage.py migrate

seed:
	$(COMPOSE) exec backend python manage.py create_default_users

ingest:
	$(COMPOSE) run --rm rag python ingest/run_ingest.py

test:
	python3 tests/test_schema_contract.py

measure:
	bash scripts/measure.sh
