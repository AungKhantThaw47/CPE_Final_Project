@echo off
REM Quick Start Script for Terraform Deployment (Windows)
REM This script provides the exact commands to build and deploy everything

echo =====================================
echo Terraform Single-Command Deployment
echo =====================================
echo.

REM Step 1: Authenticate
echo Step 1: Authenticating with Google Cloud...
gcloud auth application-default login

REM Step 2: Set project
echo.
echo Step 2: Setting project...
gcloud config set project cpe-final-project

REM Step 3: Initialize Terraform
echo.
echo Step 3: Initializing Terraform...
terraform init

REM Step 4: Apply configuration (this builds and deploys everything)
echo.
echo Step 4: Applying Terraform configuration...
echo This will:
echo   - Enable all required APIs
echo   - Create Artifact Registry
echo   - Build Docker image using Cloud Build
echo   - Push image to registry
echo   - Create storage bucket
echo   - Create service accounts
echo   - Deploy Cloud Run GPU job
echo.
terraform apply

echo.
echo =====================================
echo Deployment Complete!
echo =====================================
pause
