param(
    [string]$msg = "chore: sync intelligence platform and pipeline updates"
)

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  Dual-Repo Multi-Push (Public + Private)       " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# 1. Sync Public Intelligence Repository (Root)
Write-Host "`n[1/2] Syncing Public Repo: gujrera-intelligence..." -ForegroundColor Cyan
git add .
$statusPublic = git status --porcelain
if ($statusPublic) {
    git commit -m $msg
    git push origin main
    Write-Host "  -> Public repository pushed." -ForegroundColor Green
} else {
    Write-Host "  -> No changes in public repository." -ForegroundColor DarkGray
}

# 2. Sync Private Pipeline Repository (gujrera_pipeline)
Write-Host "`n[2/2] Syncing Private Repo: gujrera-pipeline..." -ForegroundColor Yellow
Push-Location gujrera_pipeline
git add .
$statusPrivate = git status --porcelain
if ($statusPrivate) {
    git commit -m $msg
    git push origin main
    Write-Host "  -> Private repository pushed." -ForegroundColor Green
} else {
    Write-Host "  -> No changes in private repository." -ForegroundColor DarkGray
}
Pop-Location

Write-Host "`nAll repositories synchronized successfully!`n" -ForegroundColor Green
