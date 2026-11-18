$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptDir '../..')).Path
$Config = Join-Path $Root 'config/local-model.env'
if (-not (Test-Path $Config)) { throw "Missing $Config. Copy local-model.env.example and configure model/server paths." }
$Values = @{}
Get-Content $Config | ForEach-Object {
  $line = $_.Trim()
  if ($line -match '^([A-Z0-9_]+)="?(.*?)"?$' -and -not $line.StartsWith('#')) { $Values[$matches[1]] = $matches[2] }
}
$Storage = $Values['JULIAN_STORAGE_ROOT']
if (-not $Storage) { $Storage = Split-Path -Parent $Root }
$Storage = (Resolve-Path $Storage).Path
$Key = if ([Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -eq 'Arm64') { 'windows-arm64' } else { 'windows-x86_64' }
$Server = $Values['JULIAN_LLAMA_SERVER_PATH']
if (-not $Server) { $Server = Join-Path $Storage "runtimes/llama.cpp/$Key/llama-server.exe" }
$Model = $Values['JULIAN_MODEL_PATH']
if (-not $Model) {
  $Models = @(Get-ChildItem (Join-Path $Storage 'models') -Filter '*.gguf' -File -Recurse -ErrorAction SilentlyContinue)
  if ($Models.Count -ne 1) { throw "Expected exactly one GGUF under $Storage/models; found $($Models.Count). Set JULIAN_MODEL_PATH explicitly." }
  $Model = $Models[0].FullName
}
if (-not (Test-Path $Server -PathType Leaf)) { throw "llama-server executable not found: $Server. Configure JULIAN_LLAMA_SERVER_PATH." }
if (-not (Test-Path $Model -PathType Leaf)) { throw "Model file not found: $Model" }
$Port = if ($Values['JULIAN_LLM_PORT']) { $Values['JULIAN_LLM_PORT'] } else { '8081' }
$Context = if ($Values['JULIAN_CONTEXT_SIZE']) { $Values['JULIAN_CONTEXT_SIZE'] } else { '4096' }
$Gpu = if ($Values['JULIAN_GPU_LAYERS']) { $Values['JULIAN_GPU_LAYERS'] } else { '999' }
$Threads = if ($Values['JULIAN_THREADS']) { $Values['JULIAN_THREADS'] } else { '-1' }
$Existing = $null
try { $Existing = Invoke-RestMethod "http://127.0.0.1:$Port/v1/models" -TimeoutSec 2 } catch {}
if ($Existing) { Write-Host "Model endpoint already responds at port $Port; refusing duplicate startup."; exit 0 }
$LogDir = Join-Path $Storage 'logs/julian'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir 'llama-server.log'
$Args = @('-m', $Model, '--host', '127.0.0.1', '--port', $Port, '-c', $Context, '-ngl', $Gpu, '-t', $Threads, '--alias', $(if ($Values['JULIAN_LLM_MODEL']) { $Values['JULIAN_LLM_MODEL'] } else { 'qwen-local' }))
$Process = Start-Process -FilePath $Server -ArgumentList $Args -RedirectStandardOutput $Log -RedirectStandardError $Log -PassThru -WindowStyle Hidden
Set-Content -Path (Join-Path $LogDir 'llama-server.pid') -Value $Process.Id
for ($i = 0; $i -lt 90; $i++) {
  try { Invoke-RestMethod "http://127.0.0.1:$Port/v1/models" -TimeoutSec 2 | Out-Null; Write-Host "PASS: model endpoint reachable at http://127.0.0.1:$Port/v1/models"; exit 0 } catch {}
  if ($Process.HasExited) { throw "llama-server exited. Inspect $Log" }
  Start-Sleep -Seconds 1
}
throw "llama-server not ready after 90 seconds. Inspect $Log"
