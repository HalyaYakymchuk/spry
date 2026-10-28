COMPOSE := docker compose

.PHONY: help up down build build-frontend build-backend logs ps migrate revision test test-backend test-frontend lint fmt clean shell-backend shell-db infra-plan generate-env env deploy-infra deploy-auth deploy-cognito deploy-reports deploy-parser deploy-backend destroy-backend logs-backend migrate-backend cert domain deploy-frontend destroy-frontend logs-parser test-agenda-lambda verify-step4 github-role report-now llm-hello parse

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Start the whole stack (detached)
	$(COMPOSE) up -d --build

down: ## Stop the stack
	$(COMPOSE) down

clean: ## Stop the stack and wipe the database volume
	$(COMPOSE) down -v

build: ## Rebuild images
	$(COMPOSE) build

build-frontend: ## Build frontend static export with configuration from Terraform outputs
	@COGNITO_CLIENT_ID=$$(terraform -chdir=infra output -raw user_pool_client_id 2>/dev/null || echo "$${COGNITO_CLIENT_ID}") \
	 COGNITO_DOMAIN=$$(terraform -chdir=infra output -raw cognito_domain 2>/dev/null || echo "$${COGNITO_DOMAIN}") \
	 PARSER_FUNCTION_URL=$$(terraform -chdir=infra output -raw parser_function_url 2>/dev/null || echo "$${PARSER_FUNCTION_URL}") \
	 cd frontend && NEXT_OUTPUT=export \
	  NEXT_PUBLIC_COGNITO_CLIENT_ID="$$COGNITO_CLIENT_ID" \
	  NEXT_PUBLIC_COGNITO_DOMAIN="$$COGNITO_DOMAIN" \
	  NEXT_PUBLIC_PARSER_URL="$$PARSER_FUNCTION_URL" \
	  pnpm build

build-backend: ## Build backend docker image
	$(COMPOSE) build backend

logs: ## Tail all logs
	$(COMPOSE) logs -f

ps: ## Show service status
	$(COMPOSE) ps

migrate: ## Apply migrations
	$(COMPOSE) exec backend alembic upgrade head

revision: ## Autogenerate a migration: make revision m="add x"
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	$(COMPOSE) exec backend pytest

test-frontend: ## Run frontend tests
	$(COMPOSE) exec frontend pnpm test

lint: ## Lint both sides
	$(COMPOSE) exec backend ruff check .
	$(COMPOSE) exec frontend pnpm lint

fmt: ## Format both sides
	$(COMPOSE) exec backend ruff format .
	$(COMPOSE) exec frontend pnpm format

shell-backend: ## Shell into the backend container
	$(COMPOSE) exec backend bash

shell-db: ## psql into the database
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-postgres} -d $${POSTGRES_DB:-spry}

infra-plan: ## Preview infrastructure changes locally (remote apply runs in HCP Terraform)
	cd infra && terraform plan

generate-env: ## Generate / sync .env with configuration values from Terraform outputs
	@"$(PYTHON)" scripts/generate_env.py

env: generate-env ## Alias for generate-env

# Legacy CloudFormation targets redirected to unified Terraform infra-plan
deploy-infra: infra-plan
deploy-auth: infra-plan
deploy-cognito: infra-plan
deploy-reports: infra-plan
deploy-parser: infra-plan

deploy-backend: ## Build + push the image, roll the Lambda (function URL + Aurora), migrate, write BACKEND_URL to .env
	@COGNITO_USER_POOL_ID=$$(terraform -chdir=infra output -raw user_pool_id 2>/dev/null || echo "$${COGNITO_USER_POOL_ID}") \
	 COGNITO_CLIENT_ID=$$(terraform -chdir=infra output -raw user_pool_client_id 2>/dev/null || echo "$${COGNITO_CLIENT_ID}") \
	 ./scripts/deploy-backend.sh

destroy-backend: ## Delete the backend stack, Aurora cluster included
	./scripts/destroy-backend.sh

logs-backend: ## Tail the deployed backend's CloudWatch logs
	aws logs tail /aws/lambda/$${PROJECT_NAME:-peach}-backend --follow --since 10m

migrate-backend: ## Re-run migrations on the deployed backend (deploy-backend already does)
	aws lambda invoke --function-name $${PROJECT_NAME:-peach}-backend \
		--cli-binary-format raw-in-base64-out --payload '{"action":"migrate"}' /dev/stdout

cert: ## Request + DNS-validate a us-east-1 certificate for the frontend: make cert DOMAIN=app.example.com
	./scripts/domain-frontend.sh cert

domain: ## Assign a custom domain to the frontend: make domain DOMAIN=app.example.com
	./scripts/domain-frontend.sh domain

deploy-frontend: ## Build the static export against BACKEND_URL and ship it to S3 + CloudFront
	@COGNITO_CLIENT_ID=$$(terraform -chdir=infra output -raw user_pool_client_id 2>/dev/null || echo "$${COGNITO_CLIENT_ID}") \
	 COGNITO_DOMAIN=$$(terraform -chdir=infra output -raw cognito_domain 2>/dev/null || echo "$${COGNITO_DOMAIN}") \
	 PARSER_FUNCTION_URL=$$(terraform -chdir=infra output -raw parser_function_url 2>/dev/null || echo "$${PARSER_FUNCTION_URL}") \
	 ./scripts/deploy-frontend.sh

destroy-frontend: ## Delete the frontend stack (bucket + distribution)
	./scripts/destroy-frontend.sh

logs-parser: ## Tail the agenda parser Lambda CloudWatch logs
	aws logs tail /aws/lambda/$${PROJECT_NAME:-peach}-agenda-parser --follow --since 10m

test-agenda-lambda: ## Run verification tests against deployed agenda parser Function URL (200, 401, 413)
	@"$(PYTHON)" scripts/test_agenda_lambda.py

verify-step4: ## Verify Part 4 Step 4: The screen (paste, check, save flow)
	@"$(PYTHON)" scripts/verify_step4_screen_flow.py

github-role: ## Create the IAM role GitHub Actions assumes to deploy (OIDC, no keys)
	./scripts/github-role.sh

report-now: ## Trigger on-demand weekly report generation: make report-now WEEK=2026-W39
	@QUEUE_URL=$$(cd infra && terraform output -raw report_requests_queue_url); \
	aws sqs send-message \
	  --queue-url "$$QUEUE_URL" \
	  --region eu-north-1 \
	  --message-body '{"week": "$(WEEK)", "source": "manual"}'

PARSER_MODEL ?= eu.anthropic.claude-haiku-4-5-20251001-v1:0
AWS_REGION ?= eu-north-1
VENV_PYTHON := $(shell if [ -f "backend/.venv/Scripts/python.exe" ]; then echo "backend/.venv/Scripts/python.exe"; elif [ -f "backend/.venv/bin/python" ]; then echo "backend/.venv/bin/python"; else which python 2>/dev/null || echo python; fi)
PYTHON ?= $(VENV_PYTHON)

llm-hello: ## Test Bedrock Anthropic Claude connectivity in eu-north-1: make llm-hello
	@PARSER_MODEL="$(PARSER_MODEL)" AWS_REGION="$(AWS_REGION)" "$(PYTHON)" backend/scripts/llm_hello.py

TEXT ?= Meeting tomorrow at 10am to discuss Q4 budget. John leads for 30m. Action: Sarah to send sheet by Friday.

parse: ## Parse meeting agenda text using Bedrock Claude: make parse TEXT="..."
	@PARSER_MODEL="$(PARSER_MODEL)" AWS_REGION="$(AWS_REGION)" "$(PYTHON)" backend/scripts/run_parse.py --text "$(TEXT)"
