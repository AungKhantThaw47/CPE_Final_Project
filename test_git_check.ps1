Set-Location 'D:\workspace\CPE_Final_Project'

# Get current git commit (use github_sha if provided, otherwise HEAD)
$targetCommit = ''
if ([string]::IsNullOrEmpty($targetCommit)) {
  try {
    $targetCommit = (git rev-parse --short HEAD 2>$null)
    if (-not $targetCommit) { $targetCommit = "nogit" }
  } catch {
    $targetCommit = "nogit"
  }
} else {
  # Shorten the full GitHub SHA
  $targetCommit = $targetCommit.Substring(0, [Math]::Min(7, $targetCommit.Length))
}

# Get relative path to codebase directory
$codebasePath = 'D:\workspace\CPE_Final_Project\Codebase_Container\crawler_job'

# Check if we're in a git repo
if ($targetCommit -eq "nogit") {
  $hasChanges = "true"
  $lastCommit = "nogit"
} else {
  # Check for uncommitted changes (only relevant for local, not CI)
  $isCI = '' -ne ''
  if (-not $isCI) {
    try {
      $gitChanges = (git status --porcelain $codebasePath 2>$null)
      if ($gitChanges) {
        $hasChanges = "true"
        $lastCommit = $targetCommit
        $result = @{
          has_changes = $hasChanges
          git_commit = $lastCommit
        }
        $result | ConvertTo-Json -Compress
        exit 0
      }
    } catch {
      $hasChanges = "true"
      $lastCommit = $targetCommit
      $result = @{
        has_changes = $hasChanges
        git_commit = $lastCommit
      }
      $result | ConvertTo-Json -Compress
      exit 0
    }
  }
  
  # Find the last commit that actually changed the codebase directory
  try {
    # Check if current commit changed the codebase
    $commitDiff = (git diff-tree --no-commit-id --name-only -r $targetCommit -- $codebasePath 2>$null)
    if ($commitDiff) {
      # Current commit has changes
      $lastCommit = $targetCommit
    } else {
      # Walk back from target commit to find last commit that changed the codebase
      $lastCommit = (git log -1 --format=%h $targetCommit -- $codebasePath 2>$null)
      if (-not $lastCommit) {
        $lastCommit = $targetCommit
      }
    }
    $hasChanges = "false"
  } catch {
    $hasChanges = "false"
    $lastCommit = $targetCommit
  }
}

# Output JSON for Terraform
$result = @{
  has_changes = $hasChanges
  git_commit = $lastCommit
}
$result | ConvertTo-Json -Compress
