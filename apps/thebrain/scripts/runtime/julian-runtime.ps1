$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$Key = if ($env:PROCESSOR_ARCHITECTURE -match 'ARM64') { 'windows-arm64' } elseif ([System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -eq 'Arm64') { 'windows-arm64' } else { 'windows-x86_64' }
$RuntimeHome = if ($env:JULIAN_RUNTIME_HOME) { [System.IO.Path]::GetFullPath($env:JULIAN_RUNTIME_HOME) } else { Join-Path $Root '.julian-runtime' }
$Runtime = Join-Path $RuntimeHome "runtimes/$Key/python/python.exe"
$EnvPython = Join-Path $RuntimeHome 'envs/julian/Scripts/python.exe'
$Manager = Join-Path $Root 'scripts/runtime/runtime_manager.py'
if ($args.Count -eq 0) { Write-Output 'Usage: .\scripts\runtime\julian-runtime.ps1 doctor|install|check|test|run|list'; exit 2 }
$Command = $args[0]
switch ($Command) {
  'doctor' {
    if (Test-Path $Runtime) { & $Runtime $Manager doctor; exit $LASTEXITCODE }
    Write-Error "BLOCKED: managed Python runtime missing at $Runtime. No system-Python fallback is permitted."; exit 3
  }
  'list' {
    if (!(Test-Path $Runtime)) { Write-Error "BLOCKED: managed Python runtime missing at $Runtime."; exit 3 }
    & $Runtime $Manager list; exit $LASTEXITCODE
  }
  'install' {
    if (!(Test-Path $Runtime)) { Write-Error "BLOCKED: managed Python runtime missing at $Runtime."; exit 3 }
    & $Runtime $Manager create-env julian --requirements (Join-Path $Root 'requirements.txt'); exit $LASTEXITCODE
  }
  'check' { $Python = $EnvPython; if (!(Test-Path $Python)) { Write-Error 'BLOCKED: Julian app environment missing. Run install.'; exit 3 }; & $Python -m compileall -q (Join-Path $Root 'app') (Join-Path $Root 'tests') (Join-Path $Root 'main.py'); if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Write-Output 'PASS: Python syntax checks completed.' }
  'test' { $Python = $EnvPython; if (!(Test-Path $Python)) { Write-Error 'BLOCKED: Julian app environment missing. Run install.'; exit 3 }; & $Python -m pytest -q; exit $LASTEXITCODE }
  'run' { $Python = $EnvPython; if (!(Test-Path $Python)) { Write-Error 'BLOCKED: Julian app environment missing. Run install.'; exit 3 }; & $Python -m uvicorn app.main:app --host $(if ($env:JULIAN_HOST) {$env:JULIAN_HOST} else {'127.0.0.1'}) --port $(if ($env:JULIAN_PORT) {$env:JULIAN_PORT} else {'8080'}); exit $LASTEXITCODE }
  default { Write-Error "Unknown command: $Command"; exit 2 }
}
