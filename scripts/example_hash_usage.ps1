# Example Usage: Hash Module for PowerShell
# This script demonstrates how to use the Hash-Module.psm1

# Import the hash module
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Import-Module "$ScriptDir\Hash-Module.psm1" -Force

Write-Host "=== Hash Module - PowerShell Examples ===" -ForegroundColor Cyan
Write-Host ""

# Example 1: Hash a string
Write-Host "Example 1: Hashing a string" -ForegroundColor Green
$testString = "Hello, World!"
$stringHash = Get-StringHash -Content $testString
Write-Host "  String: '$testString'"
Write-Host "  SHA256: $stringHash"
Write-Host ""

# Example 2: Hash a single file
Write-Host "Example 2: Hashing a file" -ForegroundColor Green
$testFile = "$PSScriptRoot\..\README.md"
if (Test-Path $testFile) {
    $fileHash = Get-FileHash -FilePath $testFile
    Write-Host "  File: $testFile"
    Write-Host "  SHA256: $fileHash"
} else {
    Write-Host "  Skipped - README.md not found"
}
Write-Host ""

# Example 3: Hash a directory
Write-Host "Example 3: Hashing a directory" -ForegroundColor Green
$testDir = "$PSScriptRoot\..\Codebase_Container\text_clean_codebase"
if (Test-Path $testDir) {
    $result = Get-DirectoryContentHash -DirectoryPath $testDir
    Write-Host "  Directory: $testDir"
    Write-Host "  SHA256: $($result.Hash)"
    Write-Host "  Files processed: $($result.FileCount)"
} else {
    Write-Host "  Skipped - Directory not found"
}
Write-Host ""

# Example 4: Compare two hashes
Write-Host "Example 4: Comparing hashes" -ForegroundColor Green
$hash1 = Get-StringHash -Content "test123"
$hash2 = Get-StringHash -Content "test123"
$hash3 = Get-StringHash -Content "test456"
$match1 = Compare-Hashes -Hash1 $hash1 -Hash2 $hash2
$match2 = Compare-Hashes -Hash1 $hash1 -Hash2 $hash3
Write-Host "  Hash1 vs Hash2 (same content): $match1"
Write-Host "  Hash1 vs Hash3 (different content): $match2"
Write-Host ""

# Example 5: Save and read hash from file
Write-Host "Example 5: Save and read hash" -ForegroundColor Green
$tempHashFile = Join-Path $env:TEMP "test_hash.txt"
$testHash = Get-StringHash -Content "SaveMe"
Save-HashToFile -Hash $testHash -FilePath $tempHashFile
$readHash = Read-HashFromFile -FilePath $tempHashFile
$matches = Compare-Hashes -Hash1 $testHash -Hash2 $readHash
Write-Host "  Saved hash: $testHash"
Write-Host "  Read hash:  $readHash"
Write-Host "  Hashes match: $matches"
Remove-Item $tempHashFile -ErrorAction SilentlyContinue
Write-Host ""

# Example 6: MD5 hash (faster)
Write-Host "Example 6: MD5 hashing (faster but less secure)" -ForegroundColor Green
$md5Hash = Get-Md5Hash -Content "QuickHash"
Write-Host "  MD5: $md5Hash"
Write-Host ""

# Example 7: Custom exclusion patterns
Write-Host "Example 7: Custom exclusion patterns" -ForegroundColor Green
$customPatterns = @("*.txt", "*.log", "*\temp\*")
Write-Host "  Custom patterns: $($customPatterns -join ', ')"
Write-Host "  (Use with Get-DirectoryContentHash -ExclusionPatterns parameter)"
Write-Host ""

# Example 8: Get default exclusion patterns
Write-Host "Example 8: Default exclusion patterns" -ForegroundColor Green
$defaults = Get-DefaultExclusionPatterns
Write-Host "  Default exclusions:"
$defaults | ForEach-Object { Write-Host "    - $_" }
Write-Host ""

Write-Host "=== All examples completed ===" -ForegroundColor Cyan
