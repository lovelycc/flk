$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$PidFile = Join-Path $ProjectDir "instance\server.pid"
$StdoutLog = Join-Path $ProjectDir "instance\server.log"
$StderrLog = Join-Path $ProjectDir "instance\server-error.log"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCommand) {
        $PythonCommand = Get-Command py -ErrorAction SilentlyContinue
    }
    if (-not $PythonCommand) {
        throw "Python was not found. Install Python 3.10 or newer first."
    }
    & $($PythonCommand.Source) -m venv (Join-Path $ProjectDir ".venv")
    & $VenvPython -m pip install -r (Join-Path $ProjectDir "requirements.txt")
}

New-Item -ItemType Directory -Force -Path (Join-Path $ProjectDir "instance") | Out-Null

if (Test-Path -LiteralPath $PidFile) {
    $ExistingPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue
    $ExistingProcess = if ($ExistingPid) {
        Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue
    }
    $ExistingServerReady = $false
    if ($ExistingProcess) {
        try {
            $ExistingResponse = Invoke-WebRequest -Uri "http://127.0.0.1:5000" -UseBasicParsing -TimeoutSec 2
            $ExistingServerReady = $ExistingResponse.StatusCode -eq 200
        } catch {
            # A stale PID may have been reused by an unrelated process.
        }
    }
    if ($ExistingServerReady) {
        Write-Host "The local server is already running: http://127.0.0.1:5000" -ForegroundColor Green
        Start-Process "http://127.0.0.1:5000"
        exit 0
    }
}

$Arguments = @("-m", "flask", "--app", "app", "run", "--host", "127.0.0.1", "--port", "5000")
$Process = Start-Process -FilePath $VenvPython -ArgumentList $Arguments -WorkingDirectory $ProjectDir -WindowStyle Hidden -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -PassThru
Set-Content -LiteralPath $PidFile -Value $Process.Id

$Ready = $false
for ($Attempt = 0; $Attempt -lt 20; $Attempt++) {
    Start-Sleep -Milliseconds 250
    try {
        $Response = Invoke-WebRequest -Uri "http://127.0.0.1:5000" -UseBasicParsing -TimeoutSec 2
        if ($Response.StatusCode -eq 200) {
            $Ready = $true
            break
        }
    } catch {
        # The server may still be starting.
    }
}

if (-not $Ready) {
    throw "The server failed to start. Check instance\server-error.log."
}

Write-Host "Deployment completed: http://127.0.0.1:5000" -ForegroundColor Green
Start-Process "http://127.0.0.1:5000"
