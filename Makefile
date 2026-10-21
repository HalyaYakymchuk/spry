COMPOSE := docker compose

.PHONY: help up down build logs ps migrate revision test test-backend test-frontend lint fmt clean shell-backend shell-db deploy-cognito destroy-cognito deploy-backend destroy-backend logs-backend migrate-backend cert domain deploy-frontend destroy-frontend deploy-reports destroy-reports deploy-parser destroy-parser logs-parser test-agenda-lambda verify-step4 github-role report-now llm-hello parse

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

deploy-cognito: ## Create/update the Cognito user pool; writes COGNITO_* to .env and prints them
	./scripts/deploy-cognito.sh

destroy-cognito: ## Delete the Cognito stack, every account in the pool included
	./scripts/destroy-cognito.sh

deploy-backend: ## Build + push the image, roll the Lambda (function URL + Aurora), migrate, write BACKEND_URL to .env
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
	./scripts/deploy-frontend.sh

destroy-frontend: ## Delete the frontend stack (bucket + distribution)
	./scripts/destroy-frontend.sh

deploy-reports: ## Create/update reports stack: S3 bucket, endpoint, Lambda builder & weekly schedule
	./scripts/deploy-reports.sh

destroy-reports: ## Delete the reports stack (bucket + S3 Gateway VPC Endpoint)
	./scripts/destroy-reports.sh

deploy-parser: ## Deploy the agenda parser Lambda function and Function URL (Bedrock Claude eu-north-1)
	./scripts/deploy-parser.sh

destroy-parser: ## Delete the agenda parser stack
	./scripts/destroy-parser.sh

logs-parser: ## Tail the agenda parser Lambda CloudWatch logs
	aws logs tail /aws/lambda/$${PROJECT_NAME:-peach}-agenda-parser --follow --since 10m

test-agenda-lambda: ## Run verification tests against deployed agenda parser Function URL (200, 401, 413)
	@"$(PYTHON)" scripts/test_agenda_lambda.py

verify-step4: ## Verify Part 4 Step 4: The screen (paste, check, save flow)
	@"$(PYTHON)" scripts/verify_step4_screen_flow.py

github-role: ## Create the IAM role GitHub Actions assumes to deploy (OIDC, no keys)
	./scripts/github-role.sh

report-now: ## Trigger on-demand weekly report generation: make report-now WEEK=2026-W39
	@QUEUE_URL=$$(aws cloudformation describe-stacks --stack-name peach-reports --region eu-north-1 --query "Stacks[0].Outputs[?OutputKey=='ReportRequestsQueueUrl'].OutputValue" --output text); \
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

