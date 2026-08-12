# 后台运行用例同步脚本（运维入口）
# 用法:
#   全量重建: powershell -File run_sync_background.ps1
#   增量同步: powershell -File run_sync_background.ps1 -Script sync_cases_incremental.py
#   指定用例: powershell -File run_sync_background.ps1 -Script sync_cases_incremental.py -ScriptArgs "--case-ids 101,102"

param(
    [string]$Script = "sync_cases_to_engines.py",
    [string]$ScriptArgs = ""
)

$env:HF_ENDPOINT = "https://hf-mirror.com"
$env:PYTHONUNBUFFERED = "1"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

$base = [System.IO.Path]::GetFileNameWithoutExtension($Script)
$stdout = Join-Path $projectRoot "$base`_run.log"
$stderr = Join-Path $projectRoot "$base`_run_err.log"

# 删除旧日志
Remove-Item $stdout, $stderr -ErrorAction SilentlyContinue

Write-Host "Starting sync in background: $Script $ScriptArgs"
Write-Host "  Log: $stdout"

$argList = @("-u", "scripts/$Script")
if ($ScriptArgs) {
    $argList += $ScriptArgs.Split(" ")
}

$p = Start-Process -FilePath "python" -ArgumentList $argList -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -NoNewWindow

Write-Host "PID: $($p.Id)"
Write-Host "Waiting for completion... (may take several minutes)"

# 等待完成
$p.WaitForExit()

Write-Host ""
Write-Host "=== Sync finished with exit code $($p.ExitCode) ==="
Write-Host ""
Write-Host "--- Last 30 lines of output ---"
Get-Content $stdout -Tail 30
Write-Host ""
Write-Host "--- Last 10 lines of errors ---"
Get-Content $stderr -Tail 10
