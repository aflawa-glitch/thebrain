# Relocatable Julian launcher for Windows PowerShell 5.1+. No registry/system changes.
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptDir '..')).Path
$Config = if ($env:JULIAN_PORTABLE_CONFIG) { $env:JULIAN_PORTABLE_CONFIG } else { Join-Path $Root 'config/portable.env' }
function Stop-Julian([string]$Message) { throw "[Julian] BLOCKED: $Message" }
if (-not (Test-Path (Join-Path $Root 'JULIAN_PORTABLE_ROOT'))) { Stop-Julian "Portable root marker missing: $Root" }
if (-not (Test-Path (Join-Path $Root 'app/main.py')) -or -not (Test-Path (Join-Path $Root 'main.py'))) { Stop-Julian "Application files missing under discovered root: $Root" }
if (-not (Test-Path $Config)) { Stop-Julian "Config missing: $Config. Copy portable.env.example to portable.env and edit it." }
# Parse KEY=VALUE as data; never dot-source or execute the config.
$Settings = @{}
foreach ($Line in Get-Content -LiteralPath $Config) {
  $Trimmed = $Line.Trim()
  if (-not $Trimmed -or $Trimmed.StartsWith('#') -or -not $Trimmed.Contains('=')) { continue }
  $Pair = $Trimmed -split '=', 2
  $Settings[$Pair[0].Trim()] = $Pair[1].Trim()
}
function Get-Setting([string]$Name, [string]$EnvName = '') {
  if ($EnvName -and [Environment]::GetEnvironmentVariable($EnvName)) { return [Environment]::GetEnvironmentVariable($EnvName) }
  if ($Settings.ContainsKey($Name)) { return $Settings[$Name] }
  return ''
}
function Resolve-PortablePath([string]$Value) {
  if (-not $Value) { return '' }
  if ([IO.Path]::IsPathRooted($Value)) { return $Value }
  return Join-Path $Root $Value
}
$Python = Resolve-PortablePath (Get-Setting 'PYTHON_PATH' 'JULIAN_PYTHON_PATH')
$Llama = Resolve-PortablePath (Get-Setting 'LLAMA_SERVER_PATH' 'JULIAN_LLAMA_SERVER_PATH')
$Model = Resolve-PortablePath (Get-Setting 'MODEL_PATH' 'JULIAN_MODEL_PATH')
$LlmHost = Get-Setting 'LLM_HOST' 'JULIAN_LLM_HOST'; $LlmPort = Get-Setting 'LLM_PORT' 'JULIAN_LLM_PORT'; $LlmModel = Get-Setting 'LLM_MODEL' 'JULIAN_LLM_MODEL'
$AppHost = Get-Setting 'APP_HOST' 'JULIAN_HOST'; $AppPort = Get-Setting 'APP_PORT' 'JULIAN_PORT'
$Context = Get-Setting 'CONTEXT_SIZE' 'JULIAN_CONTEXT_SIZE'; $GpuLayers = Get-Setting 'GPU_LAYERS' 'JULIAN_GPU_LAYERS'
$Enabled = Get-Setting 'LLM_ENABLED' 'JULIAN_LLM_ENABLED'; $SearchEnabled = Get-Setting 'WEB_SEARCH_ENABLED' 'JULIAN_WEB_SEARCH_ENABLED'
$Timeout = [int](Get-Setting 'STARTUP_TIMEOUT_SECONDS' 'JULIAN_STARTUP_TIMEOUT_SECONDS')
$DataValue = Get-Setting 'DATA_DIR' 'JULIAN_DATA_DIR'; $LogValue = Get-Setting 'LOG_DIR' 'JULIAN_LOG_DIR'
$DataDir = Resolve-PortablePath $DataValue; $LogDir = Resolve-PortablePath $LogValue
if (-not (Test-Path $Python -PathType Leaf)) { Stop-Julian "Configured Python runtime missing: $Python. No system-Python fallback was attempted." }
if (-not (Test-Path $Llama -PathType Leaf)) { Stop-Julian "Configured llama-server missing: $Llama" }
if (-not (Test-Path $Model -PathType Leaf)) { Stop-Julian "Configured model file missing: $Model" }
if ($Enabled.ToLowerInvariant() -notin @('true','1','yes','on')) { Stop-Julian 'LLM_ENABLED is false. Refusing a silent quality downgrade.' }
if ($LlmPort -eq $AppPort) { Stop-Julian 'LLM_PORT and APP_PORT must differ.' }
& $Python -c 'import fastapi, uvicorn, httpx, pypdf' 2>$null
if ($LASTEXITCODE -ne 0) { Stop-Julian "Dependencies missing in configured interpreter: $Python. No packages were installed." }
New-Item -ItemType Directory -Force -Path $DataDir,$LogDir,(Join-Path $Root 'cache'),(Join-Path $Root 'backups') | Out-Null
$env:JULIAN_HOST = $AppHost; $env:JULIAN_PORT = $AppPort; $env:JULIAN_DATA_DIR = $DataDir
$env:JULIAN_LLM_BASE_URL = "http://${LlmHost}:${LlmPort}/v1"; $env:JULIAN_LLM_ENABLED = 'true'; $env:JULIAN_WEB_SEARCH_ENABLED = $SearchEnabled
$env:JULIAN_PORTABLE_ROOT = $Root; $env:PYTHONPATH = $Root
$LlmOut = Join-Path $LogDir 'llama-server.stdout.log'; $LlmErr = Join-Path $LogDir 'llama-server.stderr.log'
$AppOut = Join-Path $LogDir 'julian-backend.stdout.log'; $AppErr = Join-Path $LogDir 'julian-backend.stderr.log'
$LlmProcess = $null; $AppProcess = $null
try {
  $LlmProcess = Start-Process -FilePath $Llama -ArgumentList @('-m', $Model, '--host', $LlmHost, '--port', $LlmPort, '-c', $Context, '--n-gpu-layers', $GpuLayers) -PassThru -NoNewWindow -RedirectStandardOutput $LlmOut -RedirectStandardError $LlmErr
  $Ready = $false
  for ($i=0; $i -lt $Timeout; $i++) {
    if ($LlmProcess.HasExited) { Stop-Julian "llama-server exited; inspect $LlmErr" }
    try { Invoke-RestMethod "http://${LlmHost}:${LlmPort}/v1/models" -TimeoutSec 2 | Out-Null; $Ready = $true; break } catch { Start-Sleep -Seconds 1 }
  }
  if (-not $Ready) { Stop-Julian "Model API did not become ready; inspect $LlmErr" }
  if (-not $LlmModel -or $LlmModel -eq 'auto') {
    try { $ModelList = Invoke-RestMethod "http://${LlmHost}:${LlmPort}/v1/models" -TimeoutSec 5; $LlmModel = [string]$ModelList.data[0].id } catch { $LlmModel = '' }
    if (-not $LlmModel) { Stop-Julian 'Model API is reachable but returned no model identifier. Set LLM_MODEL explicitly after inspecting /v1/models.' }
  }
  $env:JULIAN_LLM_MODEL = $LlmModel
  Write-Host "[Julian] Model API ready; configured model identifier: $LlmModel"
  $AppProcess = Start-Process -FilePath $Python -ArgumentList @('-m','uvicorn','app.main:app','--host',$AppHost,'--port',$AppPort) -WorkingDirectory $Root -PassThru -NoNewWindow -RedirectStandardOutput $AppOut -RedirectStandardError $AppErr
  $Ready = $false
  for ($i=0; $i -lt $Timeout; $i++) {
    if ($AppProcess.HasExited) { Stop-Julian "Julian backend exited; inspect $AppErr" }
    try {
      $Health = Invoke-RestMethod "http://${AppHost}:${AppPort}/api/health" -TimeoutSec 2
      if ($Health.status -eq 'ok' -and $Health.model.status -eq 'reachable') { $Ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 1
  }
  if (-not $Ready) { Stop-Julian "Backend/model health did not pass; inspect $AppErr and $LlmErr" }
  Write-Host "[Julian] READY: http://${AppHost}:${AppPort}/"
  Write-Host '[Julian] Press Ctrl+C to stop the processes started by this launcher.'
  if ((Get-Setting 'OPEN_BROWSER').ToLowerInvariant() -in @('true','1','yes','on')) { Start-Process "http://${AppHost}:${AppPort}/" }
  while (-not $AppProcess.HasExited) {
    if ($LlmProcess.HasExited) { Stop-Julian "Model server exited unexpectedly; inspect $LlmErr" }
    Start-Sleep -Milliseconds 500
  }
  if ($AppProcess.ExitCode -ne 0) { Stop-Julian "Backend exited with code $($AppProcess.ExitCode); inspect $AppErr" }
} finally {
  if ($AppProcess -and -not $AppProcess.HasExited) { Stop-Process -Id $AppProcess.Id -ErrorAction SilentlyContinue; $AppProcess.WaitForExit() }
  if ($LlmProcess -and -not $LlmProcess.HasExited) { Stop-Process -Id $LlmProcess.Id -ErrorAction SilentlyContinue; $LlmProcess.WaitForExit() }
  Write-Host '[Julian] Stopped only the processes started by this launcher.'
}
