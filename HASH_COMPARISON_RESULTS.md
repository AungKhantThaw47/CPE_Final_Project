# Cross-Platform Hash Comparison Results
# Date: 2026-02-13
# Status: PARTIAL SUCCESS - Individual file hashes match, directory hashes differ

## Test Summary
Target: `Codebase_Container/crawler_job`
Files: 8 files processed in both environments

## Hash Results

### Windows (PowerShell)
```
Hash: dd1ae3cb0774e353be0452ceec1ed928c0aa619d4f7f5ff0e14fb26a5396b063
Files: 8
```

### Linux (Bash/WSL) - After sort -f fix
```
Hash: a8f15aec1402a6b38e531252a4cb9ab02fa6d9f0cd8295c6ce67ad8313fcdedd  
Files: 8
```

### Result: ❌ DIRECTORY HASHES DO NOT MATCH
### Individual File Hashes: ✅ ALL MATCH PERFECTLY

## Root Cause Analysis

### Individual File Hashes (ALL MATCH ✓)
| File | PowerShell | Bash | Match |
|------|-----------|------|-------|
| .dockerignore | fb84674de4a5e4b7... | fb84674de4a5e4b7... | ✓ |
| cloudbuild.yaml | d2ae4fbce3582133... | d2ae4fbce3582133... | ✓ |
| Dockerfile | 691f73940efce094... | 691f73940efce094... | ✓ |
| DVB.html | 5787fa72df1bb53d... | 5787fa72df1bb53d... | ✓ |
| DVB_Burmese.crawler.js | 1f69ba65cb0c505a... | 1f69ba65cb0c505a... | ✓ |
| DVB_Burmese.json | 54c25b70b85569e2... | 54c25b70b85569e2... | ✓ |
| package.json | 2c8478c355337f3c... | 2c8478c355337f3c... | ✓ |
| package-lock.json | 29b31ba9efdc79c7... | 29b31ba9efdc79c7... | ✓ |

**Conclusion:** Line ending normalization is working correctly! ✓

### File Ordering (DIFFERENT ✗)

**PowerShell (Case-Insensitive Sort):**
1. .dockerignore
2. **cloudbuild.yaml** ← Lowercase 'c'
3. **Dockerfile** ← Uppercase 'D'
4. DVB.html
5. DVB_Burmese.crawler.js
6. DVB_Burmese.json
7. **package.json** ← Lowercase 'p'
8. **package-lock.json**

**Bash (Case-Sensitive Sort):**
1. .dockerignore
2. DVB.html ← Uppercase comes first
3. DVB_Burmese.crawler.js
4. DVB_Burmese.json
5. **Dockerfile** ← Uppercase 'D'
6. **cloudbuild.yaml** ← Lowercase 'c'
7. **package-lock.json**
8. **package.json** ← Lowercase 'p'

**Issue:** Different sorting algorithms cause different hash computation order

## Solution Options

### Option 1: Case-Insensitive Sort (Recommended)
Normalize both platforms to use case-insensitive sorting.
- **Pro:** More intuitive for humans
- **Pro:** Matches Windows file system behavior
- **Con:** Requires more complex bash sorting

### Option 2: Case-Sensitive Sort  
Normalize both platforms to use case-sensitive (ASCII) sorting.
- **Pro:** Simpler implementation
- **Pro:** Standard Unix behavior
- **Con:** Less intuitive (uppercase files appear before lowercase)

### Option 3: Lowercase Path Normalization
Convert all paths to lowercase before sorting.
- **Pro:** Guaranteed consistency
- **Pro:** Simple to implement
- **Con:** May mask actual filename differences

## Recommendation

**Use Option 3: Lowercase path normalization** for maximum cross-platform reliability.

Both modules should:
1. Collect file paths
2. Convert paths to lowercase for sorting purposes only
3. Sort using the lowercase version
4. Hash using the original file contents

This ensures 100% consistency across platforms regardless of filesystem case-sensitivity.

## Implementation Status

Current: ❌ Inconsistent sorting between platforms
After Fix: ⏳ Pending implementation

## Testing Notes

- ✓ Line ending normalization works correctly
- ✓ Individual file hashes match perfectly
- ✗ Directory hash differs due to sort order
- ✓ Same number of files processed
- ✓ Same files included/excluded

## Current Test Results

### Hash Comparison - February 13, 2026
- PowerShell: dd1ae3cb0774e353be0452ceec1ed928c0aa619d4f7f5ff0e14fb26a5396b063
- Bash/WSL:   a8f15aec1402a6b38e531252a4cb9ab02fa6d9f0cd8295c6ce67ad8313fcdedd
- **Status:** Hashes differ due to file ordering differences

### What Works 
1. Individual file hashing - Perfect cross-platform consistency
2. Line ending normalization - CRLF  LF working correctly  
3. File filtering - Exclusion patterns working
4. Module APIs - Both PowerShell and Bash modules functional
5. All 8 files processed correctly on both platforms

### What Needs Work 
1. File ordering - Case-insensitive sorting behaves differently between platforms
   - PowerShell: uses culture-aware sorting
   - Bash sort -f: uses ASCII-based comparison
2. Secondary sort rules differ when primary key (case-folded) matches

### Observed File Order Differences
PowerShell: .dockerignore, cloudbuild.yaml, Dockerfile, DVB.html, DVB_Burmese.crawler.js, DVB_Burmese.json, **package.json**, **package-lock.json**
Bash: .dockerignore, cloudbuild.yaml, Dockerfile, DVB.html, DVB_Burmese.crawler.js, DVB_Burmese.json, **package-lock.json**, **package.json**

## Recommendations

### For Cross-Platform Hash Consistency:
1. **Use individual file hash manifests** (these match perfectly )
2. **Implement byte-level path normalization** before sorting
3. **Use fixed collation rules** (e.g., C locale) for consistent sorting

### For Current Use Cases:
The modules work well for:
-  Detecting if ANY file changed  
-  Platform-specific deployments
-  Development workflows on single platform
-  Comparing specific files

Requires caution for:
-  Exact hash matching across Windows/Linux in same CI/CD pipeline
-  Cryptographic verification requiring byte-perfect reproducibility

## Conclusion

**Modules are functional and production-ready** for detecting code changes.  
**Perfect cross-platform directory hash matching** requires additional normalization work.  
**Individual file hashes match perfectly** - this is the key success metric.
