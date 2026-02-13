# Simple Test for Terraform Hash Integration
Import-Module .\scripts\Hash-Module.psm1 -Force

$testPath = ".\Codebase_Container\crawler_job"
$result = Get-DirectoryContentHash -DirectoryPath $testPath

$output = @{
    content_hash = $result.Hash
    file_count = $result.FileCount.ToString()
} | ConvertTo-Json -Compress

Write-Host "Output for Terraform:" -ForegroundColor Cyan
Write-Host $output
Write-Host ""
Write-Host "Hash: $($result.Hash)" -ForegroundColor Green
Write-Host "Files: $($result.FileCount)" -ForegroundColor Green
