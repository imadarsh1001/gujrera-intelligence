param(
    [string]$msg = "chore: sync intelligence platform and pipeline updates",
    [switch]$AllowNonMain
)

# Branch-safe dual-repo sync: fetch -> guard branch -> stage/commit ->
# non-fast-forward check -> push HEAD:main -> verify remote ref matches.
# The two pushes are independent; a failure is reported, never auto-retried.

function Sync-Repo {
    param([string]$Path, [string]$Name)

    Push-Location $Path
    try {
        Write-Host "`n=== Syncing $Name ===" -ForegroundColor Cyan

        git fetch origin | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  FETCH FAILED - aborting $Name." -ForegroundColor Red
            return $false
        }

        $branch = git rev-parse --abbrev-ref HEAD
        if ($branch -ne "main" -and -not $AllowNonMain) {
            Write-Host "  ABORTED: current branch is '$branch', not 'main'." -ForegroundColor Red
            Write-Host "  Either commit on main, re-run with -AllowNonMain, or push explicitly:" -ForegroundColor Red
            Write-Host "    git push origin ${branch}:main" -ForegroundColor Red
            return $false
        }

        git add . | Out-Null
        if (git status --porcelain) {
            git commit -m $msg | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  COMMIT FAILED - aborting $Name." -ForegroundColor Red
                return $false
            }
        }

        $counts = (git rev-list --left-right --count "HEAD...origin/main") -split "\s+"
        $behind = [int]$counts[1]
        if ($behind -gt 0) {
            Write-Host "  ABORTED: origin/main is $behind commit(s) ahead of local '$branch'. Reconcile first:" -ForegroundColor Red
            Write-Host "    git pull --rebase origin main" -ForegroundColor Red
            return $false
        }

        git push origin HEAD:main | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  PUSH FAILED - aborting $Name." -ForegroundColor Red
            return $false
        }

        $remoteSha = ((git ls-remote origin refs/heads/main) -split "\t")[0]
        if ($remoteSha -ne (git rev-parse HEAD)) {
            Write-Host "  WARNING: remote main does not match local HEAD after push." -ForegroundColor Red
            return $false
        }

        Write-Host "  -> $Name pushed (HEAD:main, remote verified)." -ForegroundColor Green
        return $true
    }
    finally {
        Pop-Location
    }
}

$pipelinePath = if (Test-Path "$PSScriptRoot\..\gujrera_pipeline") { "$PSScriptRoot\..\gujrera_pipeline" } else { "$PSScriptRoot\gujrera_pipeline" }
$okPublic = Sync-Repo -Path "." -Name "Public Repo: gujrera-intelligence"
$okPrivate = Sync-Repo -Path $pipelinePath -Name "Private Repo: gujrera-pipeline"

if ($okPublic -and $okPrivate) {
    Write-Host "`nAll repositories synchronized successfully!`n" -ForegroundColor Green
} else {
    Write-Host "`nSYNC INCOMPLETE - see messages above. Nothing was retried automatically.`n" -ForegroundColor Red
    exit 1
}
