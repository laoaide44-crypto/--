# 交付契约台 · 一键启动(**幂等**:重复双击不会起第二个服务)
#
#   已经在跑 → 只打开浏览器
#   没在跑   → 起服务、等它就绪、再打开浏览器
#
# 服务是**独立进程**启动的,所以关掉这个窗口/关掉我的会话都不影响它。
# 要停服务:任务管理器里结束那个 python.exe(或重启电脑)。
#
# 日志:同目录 `启动日志.txt`
param([switch]$NoBrowser)

$ErrorActionPreference = 'Continue'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $dir '启动日志.txt'
$port = 8501
$url = "http://127.0.0.1:$port"
$py = 'C:\Users\17612\AppData\Local\Programs\Python\Python312\python.exe'

function Write-Log([string]$m) {
    $line = "{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Write-Host $line
    try { Add-Content -Path $log -Value $line -Encoding UTF8 } catch { }
}

function Test-App {
    try {
        $r = Invoke-WebRequest -Uri "$url/_stcore/health" -UseBasicParsing -TimeoutSec 3
        return ($r.Content -match 'ok')
    } catch { return $false }
}

$isAdmin = ([Security.Principal.WindowsPrincipal] `
        [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

Write-Log "== 启动器开始(PowerShell $($PSVersionTable.PSVersion) · 用户 $env:USERNAME · 管理员 $isAdmin)"

if (-not (Test-Path $py)) {
    Write-Log "❌ 找不到 Python:$py"
    exit 2
}

if (Test-App) {
    Write-Log "服务已经在跑($url)—— 只打开浏览器,不再起第二个"
} else {
    Write-Log "服务没在跑,正在启动…"
    $sargs = @('-m', 'streamlit', 'run', 'app.py',
               '--server.port', "$port", '--server.address', '127.0.0.1',
               '--server.headless', 'true', '--browser.gatherUsageStats', 'false')
    try {
        Start-Process -FilePath $py -ArgumentList $sargs -WorkingDirectory $dir -WindowStyle Minimized
    } catch {
        Write-Log "❌ 启动失败:$($_.Exception.Message)"
        exit 3
    }
    $ok = $false
    for ($i = 1; $i -le 30; $i++) {
        Start-Sleep -Seconds 1
        if (Test-App) { $ok = $true; Write-Log "服务就绪(等了 $i 秒)"; break }
    }
    if (-not $ok) {
        Write-Log "⚠️ 等了 30 秒还没就绪。看看是不是有别的东西占着 $port 端口(或上次的 python 没退干净)"
        Write-Log "  手动排查:netstat -ano | findstr $port"
        exit 4
    }
}

if ($NoBrowser) {
    Write-Log "(-NoBrowser)不打开浏览器"
    exit 0
}

Start-Process $url
Write-Log "已打开 $url    ← 这个窗口可以直接关掉,服务不受影响"
exit 0
