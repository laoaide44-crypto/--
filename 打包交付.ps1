# 打包交付 —— 给"拷到别的电脑 / 交作品包"用
#
# 产物: D:\学习工具\西客松2026\备份\交付契约台-交付包-<日期>.zip
# 内容: 程序/ 文档/ 运行说明.md 校验.txt
# ⚠️ 绝不包含 .env.local(密钥)、__pycache__、*.pyc、日志、运行产物
#
# 跑法:  powershell -NoProfile -ExecutionPolicy Bypass -File 打包交付.ps1

param(
    [string]$CodeDir = 'D:\学习工具\Python\xihack-fde',
    [string]$DocDir = 'D:\学习工具\西客松2026',
    [string]$OutDir = 'D:\学习工具\西客松2026\备份'
)

$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyy-MM-dd'
$name = "交付契约台-交付包-$stamp"
$stage = Join-Path $env:TEMP "xihack-pkg-$stamp"
$root = Join-Path $stage $name
$zip = Join-Path $OutDir "$name.zip"

Write-Host "== 打包 ==" -ForegroundColor Cyan
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $root -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $root '程序') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $root '文档') -Force | Out-Null
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

# ---------- 1) 程序 ----------
$codeOut = Join-Path $root '程序'
$excludeFiles = @('.env.local', 'demo-cache.json', 'ui-audit.txt', '启动日志.txt', '契约-草稿.md')
$excludeDirs = @('__pycache__', '.git')

Get-ChildItem -Path $CodeDir -File | Where-Object {
    $excludeFiles -notcontains $_.Name -and $_.Extension -in @('.py', '.json', '.md', '.txt', '.cmd', '.ps1', '') -or $_.Name -eq '.gitignore'
} | ForEach-Object { Copy-Item $_.FullName -Destination $codeOut -Force }

# .streamlit 配置(不含任何密钥)
$stOut = Join-Path $codeOut '.streamlit'
New-Item -ItemType Directory -Path $stOut -Force | Out-Null
Copy-Item (Join-Path $CodeDir '.streamlit\config.toml') (Join-Path $stOut 'config.toml') -Force

# 再删一遍,防止上面的通配把不该带的带进来
foreach ($bad in $excludeFiles) {
    $p = Join-Path $codeOut $bad
    if (Test-Path $p) { Remove-Item $p -Force }
}
Get-ChildItem $codeOut -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
Get-ChildItem $codeOut -Recurse -File -Include '*.pyc' | Remove-Item -Force

# ---------- 2) 文档 ----------
Get-ChildItem -Path $DocDir -File -Filter '*.md' |
    Where-Object { $_.Name -match '^\d\d-' } |
    ForEach-Object { Copy-Item $_.FullName -Destination (Join-Path $root '文档') -Force }
$attach = Join-Path $DocDir '附件'
if (Test-Path $attach) {
    Copy-Item $attach -Destination (Join-Path $root '文档\附件') -Recurse -Force
}

# ---------- 3) 校验.txt ----------
$all = Get-ChildItem $root -Recurse -File
$lines = @()
$lines += "交付契约台 · 交付包"
$lines += "生成时间:$stamp"
$lines += "文件数:$($all.Count)"
$lines += "总大小:$([math]::Round(($all | Measure-Object Length -Sum).Sum / 1MB, 2)) MB"
$lines += ""
$lines += "== 不含以下内容(已排除) =="
$lines += "  .env.local(密钥)、__pycache__、*.pyc、启动日志.txt、ui-audit.txt、demo-cache.json(旧版缓存)"
$lines += ""
$lines += "== 文件清单 =="
$lines += ($all | ForEach-Object { $_.FullName.Substring($root.Length + 1) + "  ($([math]::Round($_.Length / 1KB, 1)) KB)" })
$lines | Set-Content -Path (Join-Path $root '校验.txt') -Encoding UTF8

# ---------- 4) 压缩 ----------
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $root -DestinationPath $zip -CompressionLevel Optimal

# ---------- 5) 自检:不许有密钥 ----------
Add-Type -AssemblyName System.IO.Compression.FileSystem
$a = [System.IO.Compression.ZipFile]::OpenRead($zip)
$names = $a.Entries | ForEach-Object { $_.FullName }
$a.Dispose()

$bad = $names | Where-Object { $_ -match '\.env\.local$' -or $_ -match '__pycache__' -or $_ -match '\.pyc$' }
if ($bad) {
    Write-Host "❌ 自检失败:包里有不该有的文件:" -ForegroundColor Red
    $bad | ForEach-Object { Write-Host "   $_" }
    exit 1
}

Write-Host "✅ 已生成:$zip" -ForegroundColor Green
Write-Host ("   条目数 {0} · 大小 {1} MB" -f $names.Count, [math]::Round((Get-Item $zip).Length / 1MB, 2))
Write-Host "   自检:不含 .env.local / __pycache__ / *.pyc"
Write-Host ""
Write-Host "包内结构:" -ForegroundColor Cyan
$names | Where-Object { ($_ -split '/').Count -le 3 } | Sort-Object | ForEach-Object { Write-Host "   $_" }
exit 0
