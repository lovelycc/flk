$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $ProjectDir "instance\server.pid"

if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host "The local server is not running."
    exit 0
}

$ServerPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue
$Process = Get-Process -Id $ServerPid -ErrorAction SilentlyContinue
if ($Process) {
    Stop-Process -Id $ServerPid
    Write-Host "The local server has stopped." -ForegroundColor Green
} else {
    Write-Host "The server process has already ended."
}
Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
