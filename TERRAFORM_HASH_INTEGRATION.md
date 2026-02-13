# Terraform Integration - Updated Hash Modules

## Summary of Changes

Successfully integrated the new cross-platform hash modules into Terraform configuration.

## What Was Changed

### 1. Created Terraform Wrapper Scripts

**PowerShell**: `scripts/terraform_compute_hash.ps1`
- Reads JSON input from stdin (Terraform external data source format)
- Calls `Get-DirectoryContentHash` from Hash-Module.psm1
- Returns JSON with `content_hash` and `file_count`

**Bash**: `scripts/terraform_compute_hash.sh`
- Reads JSON input from stdin
- Calls `hash_directory_content` from hash_module.sh
- Returns JSON with `content_hash` and `file_count`

### 2. Updated Terraform Modules

**Modified Files:**
- `modules/cloud-run-service/main.tf`
- `modules/cloud-scheduler/main.tf`

**Changes:**
- Replaced native Terraform hash computation (`fileset`, `sha256`, etc.)
- Added `data.external.content_hash` data source
- Calls new wrapper scripts with `codebase_path` parameter
- Uses ordinal byte-level sorting for cross-platform consistency

### Before:
```terraform
locals {
  codebase_files = fileset(local.codebase_directory, "**")
  filtered_files = [for f in local.codebase_files : f if ...filters...]
  files_content = join("", [for f in sort(local.filtered_files) : ...])
  content_hash_computed = sha256(local.files_content)
}
```

### After:
```terraform
data "external" "content_hash" {
  program = local.is_windows ? 
    ["PowerShell", "-File", "${path.root}/scripts/terraform_compute_hash.ps1"] : 
    ["bash", "${path.root}/scripts/terraform_compute_hash.sh"]
  query = {
    codebase_path = abspath(local.codebase_directory)
  }
}

locals {
  content_hash_computed = data.external.content_hash.result.content_hash
}
```

## Benefits

✅ **Cross-Platform Consistency** - Same hash on Windows & Linux
✅ **Ordinal Sorting** - Byte-level sorting matches across platforms
✅ **Line Ending Normalization** - Automatic CRLF → LF conversion
✅ **Reusable Logic** - Uses same hash modules as standalone scripts
✅ **Better Maintainability** - Single source of truth for hashing logic

## Hash Verification

The hash modules now produce **identical** hashes:
```
Windows (PowerShell): a8f15aec1402a6b38e531252a4cb9ab02fa6d9f0cd8295c6ce67ad8313fcdedd
Linux (Bash/WSL):     a8f15aec1402a6b38e531252a4cb9ab02fa6d9f0cd8295c6ce67ad8313fcdedd
✅ MATCH!
```

## Testing Terraform Integration

### Test Commands

```powershell
# Test PowerShell wrapper directly
'{"codebase_path":"D:\\workspace\\CPE_Final_Project\\Codebase_Container\\crawler_job"}' | 
  powershell -File .\scripts\terraform_compute_hash.ps1

# Initialize and plan with new configuration
terraform init -upgrade
terraform plan

# Verify hash consistency
terraform state show 'data.external.content_hash'
```

### Expected Output Format

```json
{
  "content_hash": "a8f15aec1402a6b38e531252a4cb9ab02fa6d9f0cd8295c6ce67ad8313fcdedd",
  "file_count": "8"
}
```

## Impact on Existing Infrastructure

### No Breaking Changes
- Hash computation logic changed but produces valid hashes
- Existing deployed resources remain unchanged
- Content change detection still works correctly

### What Happens on Next Apply
1. Terraform will detect content_hash changes (new computation method)
2. Resources may show as needing updates
3. This is expected and safe - validates new hash system works

### Recommendation
Run `terraform plan` to review changes before applying.

## File Summary

### New Files Created
- `scripts/terraform_compute_hash.ps1` - PowerShell wrapper for Terraform
- `scripts/terraform_compute_hash.sh` - Bash wrapper for Terraform  
- `scripts/Hash-Module.psm1` - PowerShell hash module (already created)
- `scripts/hash_module.sh` - Bash hash module (already created)

### Modified Files
- `modules/cloud-run-service/main.tf` - Uses external data source
- `modules/cloud-scheduler/main.tf` - Uses external data source

### Unchanged Files
- Deployment scripts still work (`get_deployed_content_hash.*`)
- Git status scripts unchanged
- Other Terraform configuration unchanged

## Next Steps

1. ✅ Hash modules created and tested
2. ✅ Cross-platform consistency verified
3. ✅ Terraform integration configured
4. ⏳ Run `terraform plan` to verify
5. ⏳ Run `terraform apply` when ready

## Troubleshooting

### If Terraform Plan Hangs
- Check that scripts are executable (`chmod +x` on Linux)
- Verify hash module paths are correct
- Test wrapper scripts independently first

### If Hashes Don't Match
- Verify both modules use ordinal sorting
- Check that line ending normalization is enabled
- Ensure same exclusion patterns applied

### If Terraform Shows Unexpected Changes
- This is expected first time after integration
- New hash computation may differ from old method
- Review plan output to confirm changes are hash-related only

## Documentation

- Full hash module docs: [HASH_MODULES_README.md](HASH_MODULES_README.md)
- Integration guide: [HASH_INTEGRATION_GUIDE.md](HASH_INTEGRATION_GUIDE.md)
- Comparison results: [HASH_COMPARISON_RESULTS.md](HASH_COMPARISON_RESULTS.md)

---

**Status**: Integration complete, ready for testing with `terraform plan`
**Date**: February 13, 2026
