# Run backend tests + frontend type check
$root = $PSScriptRoot
& "$root\apps\studio-api\.venv\Scripts\python" -m pytest "$root\apps\studio-api\tests" -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Push-Location "$root\apps\studio-ui"
npm run typecheck
Pop-Location
