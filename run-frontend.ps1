# Start the mITyStudio frontend (Vite dev server on :5173, proxies /api to :8000)
$ui = Join-Path $PSScriptRoot 'apps\studio-ui'
if (-not (Test-Path "$ui\node_modules")) {
    Write-Host 'Installing frontend dependencies...'
    Push-Location $ui; npm install; Pop-Location
}
Set-Location $ui
npm run dev
