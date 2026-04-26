SHELL := /bin/bash

TF ?= terraform
TF_VARS_FILE ?= terraform.tfvars
TF_PLAN_FILE ?= tfplan
AUTO_APPROVE ?= false
ENV_FILE ?= .env

.PHONY: help check-tools init fmt validate plan apply deploy destroy output clean post-apply restart-graph system-restart

help:
	@echo "Terraform Make targets"
	@echo "  make check-tools - Verify required CLIs are installed"
	@echo "  make init      - Initialize Terraform"
	@echo "  make fmt       - Format Terraform files"
	@echo "  make validate  - Validate Terraform configuration"
	@echo "  make plan      - Create execution plan"
	@echo "  make apply     - Apply Terraform changes"
	@echo "  make deploy    - init + plan + apply"
	@echo "  make post-apply - Print deployment summary from Terraform outputs"
	@echo "  make destroy   - Destroy Terraform-managed resources"
	@echo "  make output    - Show Terraform outputs"
	@echo "  make clean     - Remove local plan file"
	@echo "  make restart-graph - Clean and reload Neo4j graph from manifest"
	@echo "  make system-restart CONFIRM=true - Clean Firestore events, hash nodes, and all bucket objects"
	@echo ""
	@echo "Variables:"
	@echo "  TF=<binary>                (default: terraform)"
	@echo "  TF_VARS_FILE=<file>        (default: terraform.tfvars)"
	@echo "  TF_PLAN_FILE=<file>        (default: tfplan)"
	@echo "  AUTO_APPROVE=true|false    (default: false)"
	@echo "  ENV_FILE=<file>            (default: .env)"
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
