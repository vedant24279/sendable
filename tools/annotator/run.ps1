$RepoRoot = Resolve-Path "$PSScriptRoot\..\.."

Write-Host "Starting Cricket Delivery Annotator..." -ForegroundColor Cyan

if (-not (Test-Path "$RepoRoot\tools\annotator\manifest.json")) {
    Write-Host "Building manifest.json..." -ForegroundColor Yellow
    python "$RepoRoot\tools\annotator\backend\build_manifest.py"
}

Write-Host "Starting Backend on 127.0.0.1:8765..." -ForegroundColor Green
$BackendProcess = Start-Process -FilePath "python" -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload" -WorkingDirectory "$RepoRoot\tools\annotator\backend" -PassThru

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
