# Hash Module for PowerShell
# Provides reusable hashing functions for content-based operations
# Usage: Import-Module .\Hash-Module.psm1

<#
.SYNOPSIS
    Computes SHA256 hash of a string
.PARAMETER Content
    The string content to hash
.OUTPUTS
    String - Hexadecimal hash string
#>
function Get-StringHash {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true, ValueFromPipeline=$true)]
        [string]$Content
    )
    
    process {
        $hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Content)
        $hashBytes = $hashAlgorithm.ComputeHash($bytes)
        $hash = [System.BitConverter]::ToString($hashBytes).Replace("-", "").ToLower()
        $hashAlgorithm.Dispose()
        return $hash
    }
}

<#
.SYNOPSIS
    Computes SHA256 hash of a file
.PARAMETER FilePath
    Path to the file to hash
.PARAMETER NormalizeLineEndings
    If true, normalizes CRLF to LF before hashing (default: true for text files)
.OUTPUTS
    String - Hexadecimal hash string
#>
function Get-FileHash {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$FilePath,
        
        [Parameter(Mandatory=$false)]
        [bool]$NormalizeLineEndings = $true
    )
    
    if (-not (Test-Path $FilePath)) {
        throw "File not found: $FilePath"
    }
    
    $hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
    
    try {
        if ($NormalizeLineEndings) {
            # Try to read as text and normalize line endings
            try {
                $content = [System.IO.File]::ReadAllText($FilePath, [System.Text.Encoding]::UTF8)
                $normalizedContent = $content.Replace("`r`n", "`n")
                $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalizedContent)
            } catch {
                # If text read fails (binary file), read as binary
                $bytes = [System.IO.File]::ReadAllBytes($FilePath)
            }
        } else {
            $bytes = [System.IO.File]::ReadAllBytes($FilePath)
        }
        
        $hashBytes = $hashAlgorithm.ComputeHash($bytes)
        $hash = [System.BitConverter]::ToString($hashBytes).Replace("-", "").ToLower()
        return $hash
    } finally {
        $hashAlgorithm.Dispose()
    }
}

<#
.SYNOPSIS
    Gets the default file exclusion patterns for content hashing
.OUTPUTS
    Array of exclusion patterns
#>
function Get-DefaultExclusionPatterns {
    return @(
        ".build-hash*",
        "*.log",
        "*.tmp",
        "package-lock.json",
        "*\node_modules\*",
        "*/__pycache__/*",
        "*\.pytest_cache\*",
        "*\venv\*",
        "*\.venv\*",
        "*\.git\*",
        "*\.terraform\*",
        "*.tfstate*",
        "*\.DS_Store",
        "*\dist\*",
        "*\build\*"
    )
}

<#
.SYNOPSIS
    Filters files based on exclusion patterns
.PARAMETER Files
    Array of file objects to filter
.PARAMETER ExclusionPatterns
    Array of wildcard patterns to exclude (optional, uses defaults if not provided)
.OUTPUTS
    Array of filtered file objects
#>
function Get-FilteredFiles {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [System.IO.FileInfo[]]$Files,
        
        [Parameter(Mandatory=$false)]
        [string[]]$ExclusionPatterns
    )
    
    if (-not $ExclusionPatterns) {
        $ExclusionPatterns = Get-DefaultExclusionPatterns
    }
    
    $filtered = $Files | Where-Object {
        $file = $_
        $shouldInclude = $true
        
        foreach ($pattern in $ExclusionPatterns) {
            if ($file.FullName -like $pattern -or $file.Name -like $pattern) {
                $shouldInclude = $false
                break
            }
        }
        
        return $shouldInclude
    }
    
    return $filtered
}

<#
.SYNOPSIS
    Computes SHA256 hash of directory contents
.PARAMETER DirectoryPath
    Path to the directory to hash
.PARAMETER ExclusionPatterns
    Array of wildcard patterns to exclude (optional)
.PARAMETER NormalizeLineEndings
    If true, normalizes line endings for consistent cross-platform hashing (default: true)
.PARAMETER ShowProgress
    If true, outputs progress information about processing
.OUTPUTS
    Hashtable with Hash, FileCount, and ProcessedFiles
#>
function Get-DirectoryContentHash {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$DirectoryPath,
        
        [Parameter(Mandatory=$false)]
        [string[]]$ExclusionPatterns,
        
        [Parameter(Mandatory=$false)]
        [bool]$NormalizeLineEndings = $true,
        
        [Parameter(Mandatory=$false)]
        [switch]$ShowProgress
    )
    
    if (-not (Test-Path $DirectoryPath)) {
        throw "Directory not found: $DirectoryPath"
    }
    
    # Get all files recursively
    $allFiles = Get-ChildItem -Path $DirectoryPath -Recurse -File
    
    # Filter files
    $files = Get-FilteredFiles -Files $allFiles -ExclusionPatterns $ExclusionPatterns
    # Sort using ASCII ordinal comparison for cross-platform consistency with bash
    # PowerShell's Sort-Object uses culture-aware comparison, so we need manual sorting
    $fileList = [System.Collections.Generic.List[PSCustomObject]]::new()
    foreach ($file in $files) {
        $fileList.Add([PSCustomObject]@{
            File = $file
            SortKey = $file.FullName.ToLowerInvariant().Replace('\', '/')
        })
    }
    # Manual sort using CompareOrdinal for true ASCII/byte-level sorting
    $fileList.Sort({
        param($x, $y)
        [string]::CompareOrdinal($x.SortKey, $y.SortKey)
    })
    $files = $fileList | ForEach-Object { $_.File }
    
    if ($files.Count -eq 0) {
        throw "No files found in directory after filtering"
    }
    
    if ($ShowProgress) {
        Write-Host "Processing $($files.Count) files..."
    }
    
    # Create combined hash of all file contents
    $hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
    $combinedBytes = [System.Collections.Generic.List[byte]]::new()
    $processedFiles = @()
    
    try {
        foreach ($file in $files) {
            if ($ShowProgress) {
                Write-Host "  Processing: $($file.FullName)"
            }
            
            try {
                if ($NormalizeLineEndings) {
                    # Try to read as text and normalize line endings
                    try {
                        $content = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8)
                        $normalizedContent = $content.Replace("`r`n", "`n")
                        $fileBytes = [System.Text.Encoding]::UTF8.GetBytes($normalizedContent)
                    } catch {
                        # If text read fails (binary file), read as binary
                        $fileBytes = [System.IO.File]::ReadAllBytes($file.FullName)
                    }
                } else {
                    $fileBytes = [System.IO.File]::ReadAllBytes($file.FullName)
                }
                
                $combinedBytes.AddRange($fileBytes)
                $processedFiles += $file.FullName
            } catch {
                Write-Warning "Failed to process file: $($file.FullName) - $($_.Exception.Message)"
            }
        }
        
        $hashBytes = $hashAlgorithm.ComputeHash($combinedBytes.ToArray())
        $hash = [System.BitConverter]::ToString($hashBytes).Replace("-", "").ToLower()
        
        return @{
            Hash = $hash
            FileCount = $processedFiles.Count
            ProcessedFiles = $processedFiles
        }
    } finally {
        $hashAlgorithm.Dispose()
    }
}

<#
.SYNOPSIS
    Compares two hash strings
.PARAMETER Hash1
    First hash to compare
.PARAMETER Hash2
    Second hash to compare
.OUTPUTS
    Boolean - True if hashes match, false otherwise
#>
function Compare-Hashes {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Hash1,
        
        [Parameter(Mandatory=$true)]
        [string]$Hash2
    )
    
    return $Hash1.ToLower() -eq $Hash2.ToLower()
}

<#
.SYNOPSIS
    Saves hash to a file
.PARAMETER Hash
    The hash string to save
.PARAMETER FilePath
    Path where to save the hash
#>
function Save-HashToFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Hash,
        
        [Parameter(Mandatory=$true)]
        [string]$FilePath
    )
    
    $Hash | Set-Content -Path $FilePath -NoNewline -Encoding UTF8
    Write-Verbose "Hash saved to: $FilePath"
}

<#
.SYNOPSIS
    Reads hash from a file
.PARAMETER FilePath
    Path to the hash file
.OUTPUTS
    String - The hash content, or $null if file doesn't exist
#>
function Read-HashFromFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$FilePath
    )
    
    if (Test-Path $FilePath) {
        return (Get-Content -Path $FilePath -Raw).Trim()
    }
    return $null
}

<#
.SYNOPSIS
    Computes MD5 hash (faster but less secure, useful for quick comparisons)
.PARAMETER Content
    The string content to hash
.OUTPUTS
    String - Hexadecimal MD5 hash string
#>
function Get-Md5Hash {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true, ValueFromPipeline=$true)]
        [string]$Content
    )
    
    process {
        $hashAlgorithm = [System.Security.Cryptography.MD5]::Create()
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Content)
        $hashBytes = $hashAlgorithm.ComputeHash($bytes)
        $hash = [System.BitConverter]::ToString($hashBytes).Replace("-", "").ToLower()
        $hashAlgorithm.Dispose()
        return $hash
    }
}

# Export module functions
Export-ModuleMember -Function @(
    'Get-StringHash',
    'Get-FileHash',
    'Get-DefaultExclusionPatterns',
    'Get-FilteredFiles',
    'Get-DirectoryContentHash',
    'Compare-Hashes',
    'Save-HashToFile',
    'Read-HashFromFile',
    'Get-Md5Hash'
)
