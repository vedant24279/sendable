$RepoRoot = Resolve-Path "$PSScriptRoot\..\.."

Write-Host "Starting Cricket Delivery Annotator..." -ForegroundColor Cyan

# Ensure manifest exists
if (-not (Test-Path "$RepoRoot\tools\annotator\manifest.json")) {
    Write-Host "Building manifest.json..." -ForegroundColor Yellow
    python "$RepoRoot\tools\annotator\backend\build_manifest.py"
}

# Start Backend on 127.0.0.1:8765
Write-Host "Starting Backend on 127.0.0.1:8765..." -ForegroundColor Green
$BackendProcess = Start-Process -FilePath "python" -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload" -WorkingDirectory "$RepoRoot\tools\annotator\backend" -PassThru

# Wait for backend to be healthy before starting frontend
Write-Host "Waiting for Backend API to become ready..." -ForegroundColor Yellow
$BackendReady = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health" -TimeoutSec 1 -ErrorAction Stop
        if ($health.status -eq "ok") {
            $BackendReady = $true
            break
        }
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

if ($BackendReady) {
    Write-Host "Backend API is ready!" -ForegroundColor Green
} else {
    Write-Warning "Backend API took longer than expected to start; starting frontend anyway."
}

# Start Frontend
Write-Host "Starting Frontend on 127.0.0.1:5173..." -ForegroundColor Green
$FrontendProcess = Start-Process -FilePath "npm" -ArgumentList "run dev" -WorkingDirectory "$RepoRoot\tools\annotator\frontend" -PassThru

Write-Host "`nAnnotator running!" -ForegroundColor Cyan
Write-Host "  Backend API:  http://127.0.0.1:8765/docs" -ForegroundColor Gray
Write-Host "  Frontend App: http://127.0.0.1:5173" -ForegroundColor Gray
Write-Host "Press Ctrl+C or enter to stop.`n"

try {
    Wait-Process -Id $BackendProcess.Id, $FrontendProcess.Id
} finally {
    Stop-Process -Id $BackendProcess.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $FrontendProcess.Id -ErrorAction SilentlyContinue
}
