$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (Test-Path -LiteralPath $bundledPython) { $pythonExecutable=$bundledPython } else {
  $pythonCommand=Get-Command python -ErrorAction SilentlyContinue
  if (-not $pythonCommand) { throw 'Please install Python 3.11+ or open the project in Codex with bundled Python.' }
  $pythonExecutable=$pythonCommand.Source
}
& $pythonExecutable -c "from zoneinfo import ZoneInfo; ZoneInfo('Asia/Shanghai')"
if ($LASTEXITCODE -ne 0) { throw 'Time-zone data missing. Run: python -m pip install tzdata' }
Set-Location -LiteralPath $projectRoot
Write-Host 'APP: http://127.0.0.1:8881/experience'
Write-Host 'Admin: http://127.0.0.1:8881/admin'
& $pythonExecutable -B (Join-Path $projectRoot '04_研发源码/app/r4/backend/server.py') --port 8881 --db (Join-Path $projectRoot '06_验证与后续工作/负责人优化建议-隔离预览.sqlite3') --web-root (Join-Path $projectRoot '03_当前APP')
exit $LASTEXITCODE
