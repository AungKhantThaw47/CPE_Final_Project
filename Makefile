SHELL := /bin/bash

TF ?= terraform
TF_VARS_FILE ?= terraform.tfvars
TF_PLAN_FILE ?= tfplan
AUTO_APPROVE ?= false
ENV_FILE ?= .env

.PHONY: help check-tools init fmt validate plan apply deploy deploy-all destroy output clean post-apply restart-graph system-restart coordinator-range classifier-range classifier-process coordinator-daily manual-coordinator daily-pipeline manual-crawl

help:
	@echo "Terraform Make targets"
	@echo ""
	@echo "  ✨ QUICK START:"
	@echo "  make deploy-all - Format, validate, plan, apply, and show outputs (ONE COMMAND)"
	@echo ""
	@echo "  Standard targets:"
	@echo "  make check-tools - Verify required CLIs are installed"
	@echo "  make init      - Initialize Terraform"
	@echo "  make fmt       - Format Terraform files"
	@echo "  make validate  - Validate Terraform configuration"
	@echo "  make plan      - Create execution plan"
	@echo "  make apply     - Apply Terraform changes"
	@echo "  make deploy    - plan + apply (interactive)"
	@echo "  make post-apply - Print deployment summary from Terraform outputs"
	@echo "  make destroy   - Destroy Terraform-managed resources"
	@echo "  make output    - Show Terraform outputs"
	@echo "  make clean     - Remove local plan file"
	@echo ""
	@echo "  Pipeline execution (with date ranges):"
	@echo "  make coordinator-range START_DATE=DD-MM-YYYY END_DATE=DD-MM-YYYY - Run coordinator job directly for date range"
	@echo "  make classifier-range START_DATE=DD-MM-YYYY END_DATE=DD-MM-YYYY - Run crisis-classifier-job directly for date range"
	@echo "  make classifier-process PROCESS_DATE=YYYY-MM-DD - Run crisis-classifier-job for one date"
	@echo "  make daily-pipeline           - Run Cloud Workflow daily-pipeline (yesterday)"
	@echo "  make manual-coordinator START_DATE=DD-MM-YYYY END_DATE=DD-MM-YYYY - Run Cloud Workflow manual-coordinator"
	@echo "  make manual-crawl START_DATE=DD-MM-YYYY END_DATE=DD-MM-YYYY      - Alias for manual-coordinator"
	@echo "  make coordinator-daily        - Alias for daily-pipeline"
	@echo ""
	@echo "  System management:"
	@echo "  make restart-graph - Clean and reload Neo4j graph from manifest"
	@echo "  make system-restart CONFIRM=true - Clean Firestore events, hash nodes, and all bucket objects"
	@echo ""
	@echo "Variables:"
	@echo "  TF=<binary>                (default: terraform)"
	@echo "  TF_VARS_FILE=<file>        (default: terraform.tfvars)"
	@echo "  TF_PLAN_FILE=<file>        (default: tfplan)"
	@echo "  AUTO_APPROVE=true|false    (default: false)"
	@echo "  ENV_FILE=<file>            (default: .env)"
	@echo "  START_DATE=DD-MM-YYYY      (for coordinator-range)"
	@echo "  END_DATE=DD-MM-YYYY        (for coordinator-range)"
	@echo "  PROCESS_DATE=YYYY-MM-DD    (for classifier-process)"
	@echo ""
	@echo "Note:"
	@echo "  If .env exists, Make loads it before Terraform commands."
	@echo "  If terraform.tfvars is missing, commands run without -var-file"
	@echo "  (Terraform will use defaults and TF_VAR_* env vars)."
	@echo "  This project requires python3 for Terraform external data scripts."

check-tools:
	@which "$(TF)" >/dev/null 2>&1 || { echo "Missing required tool: $(TF)"; echo "Tool check failed. Install missing dependencies and retry."; exit 1; }
	@which gcloud >/dev/null 2>&1 || { echo "Missing required tool: gcloud"; echo "Tool check failed. Install missing dependencies and retry."; exit 1; }
	@which python3 >/dev/null 2>&1 || { echo "Missing required tool: python3"; echo "Tool check failed. Install missing dependencies and retry."; exit 1; }

init: check-tools
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; $(TF) init

fmt:
	$(TF) fmt -recursive

validate: init
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; $(TF) validate

plan: init
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; \
	if [ -f "$(TF_VARS_FILE)" ]; then \
		echo "Using var-file: $(TF_VARS_FILE)"; \
		$(TF) plan -var-file=$(TF_VARS_FILE) -out=$(TF_PLAN_FILE); \
	elif [ "$(TF_VARS_FILE)" = "terraform.tfvars" ]; then \
		echo "terraform.tfvars not found; running plan without -var-file"; \
		$(TF) plan -out=$(TF_PLAN_FILE); \
	else \
		echo "Error: TF_VARS_FILE '$(TF_VARS_FILE)' does not exist."; \
		exit 1; \
	fi

apply: init
ifeq ($(AUTO_APPROVE),true)
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; \
	if [ -f "$(TF_VARS_FILE)" ]; then \
		echo "Using var-file: $(TF_VARS_FILE)"; \
		$(TF) apply -var-file=$(TF_VARS_FILE) -auto-approve; \
	elif [ "$(TF_VARS_FILE)" = "terraform.tfvars" ]; then \
		echo "terraform.tfvars not found; running apply without -var-file"; \
		$(TF) apply -auto-approve; \
	else \
		echo "Error: TF_VARS_FILE '$(TF_VARS_FILE)' does not exist."; \
		exit 1; \
	fi
	@$(MAKE) post-apply TF="$(TF)"
else
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; \
	if [ -f "$(TF_VARS_FILE)" ]; then \
		echo "Using var-file: $(TF_VARS_FILE)"; \
		$(TF) apply -var-file=$(TF_VARS_FILE); \
	elif [ "$(TF_VARS_FILE)" = "terraform.tfvars" ]; then \
		echo "terraform.tfvars not found; running apply without -var-file"; \
		$(TF) apply; \
	else \
		echo "Error: TF_VARS_FILE '$(TF_VARS_FILE)' does not exist."; \
		exit 1; \
	fi
	@$(MAKE) post-apply TF="$(TF)"
endif

deploy: plan
ifeq ($(AUTO_APPROVE),true)
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; $(TF) apply -auto-approve $(TF_PLAN_FILE)
else
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; $(TF) apply $(TF_PLAN_FILE)
endif
	@$(MAKE) post-apply TF="$(TF)"

# ============================================
# Deploy Everything in One Command
# ============================================
deploy-all: check-tools fmt validate plan
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║         🚀 DEPLOYING INFRASTRUCTURE (AUTO-APPROVE)            ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; \
	$(TF) apply -auto-approve $(TF_PLAN_FILE)
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║                    ✅ DEPLOYMENT COMPLETE                      ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@$(MAKE) post-apply TF="$(TF)"
	@echo ""
	@echo "📋 Deployment Summary:"
	@echo "════════════════════════════════════════════════════════════════"
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; \
	$(TF) output -json | jq '.' 2>/dev/null | head -50
	@echo ""
	@echo "Next steps:"
	@echo "  1. Capture service URLs: make output"
	@echo "  2. Update dashboard API: see DEPLOYMENT_CHECKLIST.md"
	@echo "  3. Test pipeline: gcloud workflows run daily-pipeline --location asia-southeast1"
	@echo ""

destroy: init
ifeq ($(AUTO_APPROVE),true)
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; \
	if [ -f "$(TF_VARS_FILE)" ]; then \
		echo "Using var-file: $(TF_VARS_FILE)"; \
		$(TF) destroy -var-file=$(TF_VARS_FILE) -auto-approve; \
	elif [ "$(TF_VARS_FILE)" = "terraform.tfvars" ]; then \
		echo "terraform.tfvars not found; running destroy without -var-file"; \
		$(TF) destroy -auto-approve; \
	else \
		echo "Error: TF_VARS_FILE '$(TF_VARS_FILE)' does not exist."; \
		exit 1; \
	fi
else
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; \
	if [ -f "$(TF_VARS_FILE)" ]; then \
		echo "Using var-file: $(TF_VARS_FILE)"; \
		$(TF) destroy -var-file=$(TF_VARS_FILE); \
	elif [ "$(TF_VARS_FILE)" = "terraform.tfvars" ]; then \
		echo "terraform.tfvars not found; running destroy without -var-file"; \
		$(TF) destroy; \
	else \
		echo "Error: TF_VARS_FILE '$(TF_VARS_FILE)' does not exist."; \
		exit 1; \
	fi
endif

output:
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; $(TF) output

clean:
	rm -f $(TF_PLAN_FILE)

post-apply:
	@bash scripts/terraform_post_action.sh

restart-graph: check-tools
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; \
	python3 bootstrap/neo4j/restart_graph.py

system-restart: check-tools
	@set -a; [ ! -f "$(ENV_FILE)" ] || source "$(ENV_FILE)"; set +a; \
	bash scripts/system_restart.sh

# ============================================
# Coordinator & Crawler Range Execution
# ============================================
coordinator-range: check-tools
	@if [ -z "$(START_DATE)" ] || [ -z "$(END_DATE)" ]; then \
		echo "Error: START_DATE and END_DATE required"; \
		echo "Usage: make coordinator-range START_DATE=DD-MM-YYYY END_DATE=DD-MM-YYYY"; \
		exit 1; \
	fi
	@bash -c 'set -a; [ -f ".env" ] && source .env; set +a; \
	echo "Running coordinator for $(START_DATE) to $(END_DATE)..."; \
	gcloud run jobs execute dvb-coordinator-job \
	  --region $$TF_VAR_region \
	  --project $$TF_VAR_project_id \
	  --update-env-vars "CRAWL_START_DATE=$(START_DATE),CRAWL_END_DATE=$(END_DATE)" \
	  --wait'

classifier-range: check-tools
	@if [ -z "$(START_DATE)" ] || [ -z "$(END_DATE)" ]; then \
		echo "Error: START_DATE and END_DATE required"; \
		echo "Usage: make classifier-range START_DATE=DD-MM-YYYY END_DATE=DD-MM-YYYY"; \
		exit 1; \
	fi
	@bash -c 'set -a; [ -f ".env" ] && source .env; set +a; \
	echo "Running classifier for $(START_DATE) to $(END_DATE)..."; \
	gcloud run jobs execute crisis-classifier-job \
	  --region $$TF_VAR_region \
	  --project $$TF_VAR_project_id \
	  --update-env-vars "START_DATE=$(START_DATE),END_DATE=$(END_DATE)" \
	  --wait'

classifier-process: check-tools
	@if [ -z "$(PROCESS_DATE)" ]; then \
		echo "Error: PROCESS_DATE required"; \
		echo "Usage: make classifier-process PROCESS_DATE=YYYY-MM-DD"; \
		exit 1; \
	fi
	@bash -c 'set -a; [ -f ".env" ] && source .env; set +a; \
	echo "Running classifier for $(PROCESS_DATE)..."; \
	gcloud run jobs execute crisis-classifier-job \
	  --region $$TF_VAR_region \
	  --project $$TF_VAR_project_id \
	  --update-env-vars "PROCESS_DATE=$(PROCESS_DATE)" \
	  --wait'

# Run the Cloud Workflow daily-pipeline entrypoint
coordinator-daily: daily-pipeline

daily-pipeline: check-tools
	@bash -c 'set -a; [ -f ".env" ] && source .env; set +a; \
	echo "Running Cloud Workflow daily-pipeline..."; \
	gcloud workflows run daily-pipeline \
	  --project $$TF_VAR_project_id \
	  --location $$TF_VAR_region'

# Run the Cloud Workflow manual-coordinator entrypoint
manual-coordinator: check-tools
	@if [ -z "$(START_DATE)" ] || [ -z "$(END_DATE)" ]; then \
		echo "Error: START_DATE and END_DATE required"; \
		echo "Usage: make manual-coordinator START_DATE=DD-MM-YYYY END_DATE=DD-MM-YYYY"; \
		exit 1; \
	fi; \
	bash -c 'set -a; [ -f ".env" ] && source .env; set +a; \
	echo "Running Cloud Workflow manual-coordinator for $(START_DATE) to $(END_DATE)..."; \
	gcloud workflows run manual-coordinator \
	  --project $$TF_VAR_project_id \
	  --location $$TF_VAR_region \
	  --data "{\"start_date\":\"$(START_DATE)\",\"end_date\":\"$(END_DATE)\"}"'

# Alias that forwards to the manual workflow run
manual-crawl: manual-coordinator
