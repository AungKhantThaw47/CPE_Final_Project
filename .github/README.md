# GitHub Actions CI/CD

This directory contains the GitHub Actions configuration for automated Terraform deployment.

## Files

- **`workflows/terraform-deploy.yml`**: Main CI/CD workflow
- **`GITHUB_ACTIONS_SETUP.md`**: Complete setup instructions

## Quick Start

### 1. Prerequisites
- GCP Project with billing enabled
- GitHub repository
- Admin access to both

### 2. Setup (10 minutes)
1. Create GCP service account
2. Generate JSON key file
3. Add `GOOGLE_CREDENTIALS` secret to GitHub
4. Push changes to trigger workflow

**Detailed instructions**: [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md)

### 3. Usage

**Automatic triggers:**
- Push to `main` → Full deployment
- Open Pull Request → Plan only (results commented)
- Manual trigger → Via GitHub Actions UI

## Workflow Overview

```
┌─────────────┐
│ Push/PR     │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│  terraform-plan         │
│  • Format check         │
│  • Initialize           │
│  • Validate             │
│  • Create plan          │
│  • Comment on PR        │
└──────┬──────────────────┘
       │ (only on push to main)
       ▼
┌─────────────────────────┐
│  terraform-apply        │
│  • Apply plan           │
│  • Build Docker images  │
│  • Deploy to GCP        │
│  • Display outputs      │
└─────────────────────────┘
```

## Authentication Method

This workflow uses **Service Account JSON Key** authentication:

✅ **Simple setup** - Just create SA and download key  
✅ **Works everywhere** - No special GCP configuration  
✅ **Battle-tested** - Standard approach used widely  

**Security considerations:**
- Rotate keys every 90 days
- Store only in GitHub secrets
- Use minimal required permissions
- Enable audit logging

**Alternative**: For keyless authentication, see [Workload Identity Federation](https://cloud.google.com/blog/products/identity-security/enabling-keyless-authentication-from-github-actions)

## Build Hash System

The workflow sets `TF_VAR_github_sha` which Terraform uses to detect CI environment:

```yaml
env:
  TF_VAR_github_sha: ${{ github.sha }}
```

This triggers `.build-hash` generation with `GITHUB-` prefix:
- Local: `LOCAL-abc1234` (when `github_sha=""`)
- CI: `GITHUB-abc1234` (when `github_sha` is set)

## Security

✅ **Store keys securely** - Only in GitHub secrets, never in code  
✅ **Minimal permissions** - Use least privilege IAM roles  
✅ **Regular rotation** - Rotate keys every 90 days  
✅ **Audit logging** - Monitor service account usage  
✅ **Branch protection** - Require reviews before merge  

### Service Account Security

```bash
# List all keys for service account
gcloud iam service-accounts keys list \
  --iam-account=github-actions@PROJECT_ID.iam.gserviceaccount.com

# Delete old/unused keys
gcloud iam service-accounts keys delete KEY_ID \
  --iam-account=github-actions@PROJECT_ID.iam.gserviceaccount.com
```

**Key Rotation Schedule:**
- Review keys: Monthly
- Rotate keys: Every 90 days
- Audit access: Weekly

## Example PR Comment

When a PR is opened, the workflow comments:

```markdown
#### Terraform Format and Style 🖌 `success`
#### Terraform Initialization ⚙️ `success`
#### Terraform Validation 🤖 `success`
#### Terraform Plan 📖 `success`

<details><summary>Show Plan</summary>

Plan: 5 to add, 2 to change, 0 to destroy.

...terraform plan output...

</details>

**Build Hash Environment**: `GITHUB-abc1234`
**Commit**: 1234567890abcdef
**Pusher**: @username
**Action**: pull_request
```

## Monitoring

- **GitHub Actions**: View runs in `Actions` tab
- **GCP Console**: View builds in Cloud Build
- **Logs**: Accessible from both GitHub and GCP

## Troubleshooting

### Authentication Failed
Check:
1. `GOOGLE_CREDENTIALS` secret contains complete JSON (including `{` `}`)
2. Service account has required IAM roles
3. No extra whitespace in secret value
4. JSON is valid (test with `jq` locally)

### Terraform Error
Check:
1. Backend state bucket exists and is accessible
2. Service account has storage.admin or storage.objectAdmin
3. All required GCP APIs are enabled

### Build Failed
Check:
1. Dockerfile syntax is correct
2. cloudbuild.yaml configuration is valid
3. Service account has cloudbuild.builds.editor role
4. Build logs in GCP Console for details

## Local vs CI

| Aspect | Local Development | GitHub Actions CI |
|--------|------------------|-------------------|
| Trigger | Manual `terraform apply` | Push to main |
| Authentication | User credentials / gcloud | Service Account JSON Key |
| Build Hash | `LOCAL-<hash>` | `GITHUB-<hash>` |
| Environment Variable | `TF_VAR_github_sha=""` | `TF_VAR_github_sha=${{ github.sha }}` |
| Credentials | `~/.config/gcloud` | `GOOGLE_CREDENTIALS` secret |
| Approval | Interactive prompt | Auto-approve |

## Best Practices

1. **Always create PR first** - Get plan before applying
2. **Review PR comments** - Check terraform plan output
3. **Enable branch protection** - Require reviews before merge
4. **Monitor Cloud Build** - Watch image builds progress
5. **Use environments** - Add GitHub environment protection rules

## Related Documentation

- [Complete Setup Guide](GITHUB_ACTIONS_SETUP.md)
- [Project README](../README.md)
- [Project Instructions](../instructions.md)
