# Start the mITyStudio backend (FastAPI on :8000)
$api = Join-Path $PSScriptRoot 'apps\studio-api'
if (-not (Test-Path "$api\.venv")) {
    Write-Host 'Creating venv and installing dependencies...'
    python -m venv "$api\.venv"
    & "$api\.venv\Scripts\pip" install -r "$api\requirements.txt"
}
Set-Location $api
& "$api\.venv\Scripts\python" -m uvicorn app.main:app --reload --port 8000
