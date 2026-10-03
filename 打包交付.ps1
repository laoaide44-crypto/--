# Build a clean final submission package from this checkout.
param(
    [string]$CodeDir = $PSScriptRoot,
    [string]$DocDir = $PSScriptRoot,
    [string]$OutDir = (Join-Path $PSScriptRoot 'dist')
)
$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyy-MM-dd'
$name = "xihack-final-submission-$stamp"
$stage = Join-Path $env:TEMP "xihack-final-pkg-$stamp"
$root = Join-Path $stage $name
$zip = Join-Path $OutDir "$name.zip"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $root 'program') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $root 'docs') -Force | Out-Null
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$program = Join-Path $root 'program'
$allowed = @('.py', '.json', '.md', '.cmd', '.ps1', '.toml', '.example')
Get-ChildItem -LiteralPath $CodeDir -File | Where-Object {
    ($allowed -contains $_.Extension) -and ($_.Name -notlike 'app.py.bak*') -and ($_.Name -ne '打包交付.ps1')
} | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $program -Force }
$st = Join-Path $program '.streamlit'
New-Item -ItemType Directory -Path $st -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $CodeDir '.streamlit\config.toml') -Destination (Join-Path $st 'config.toml') -Force
$cap = Get-ChildItem -LiteralPath $CodeDir -Directory | Where-Object {
    (Test-Path (Join-Path $_.FullName 'samples')) -and ((Get-ChildItem -LiteralPath (Join-Path $_.FullName 'samples') -Filter 'SYNTHETIC_*.csv' -File -ErrorAction SilentlyContinue).Count -gt 0)
} | Select-Object -First 1
if ($cap) {
    $pack = Join-Path $program 'onsite-capability-pack'
    $samples = Join-Path $pack 'samples'
    New-Item -ItemType Directory -Path $samples -Force | Out-Null
    Get-ChildItem -LiteralPath $cap.FullName -File -Filter '*.md' | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $pack -Force }
    Get-ChildItem -LiteralPath (Join-Path $cap.FullName 'samples') -File | Where-Object { $_.Name -like 'SYNTHETIC_*.csv' -or $_.Name -eq 'README.md' } | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $samples -Force }
}
Get-ChildItem -LiteralPath $DocDir -File -Filter '*.md' | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $root 'docs') -Force }
Get-ChildItem -LiteralPath $root -Recurse -Directory | Where-Object { $_.Name -in @('__pycache__', '.git', 'dist') } | Sort-Object FullName -Descending | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object { $_.Extension -eq '.pyc' -or $_.Name -eq '.env.local' -or $_.Name -like 'app.py.bak*' } | Remove-Item -Force
$files = Get-ChildItem -LiteralPath $root -Recurse -File
$manifest = Join-Path $root 'PACKAGE_MANIFEST.txt'
$lines = @('XiHack 2026 final submission package', "Generated: $stamp", "File count before manifest: $($files.Count)", "Total bytes before manifest: $((($files | Measure-Object Length -Sum).Sum))", '', 'Excluded: secrets, pyc, caches, git metadata, logs, frozen snapshots, old backups.', 'Primary scenario: fast-delivery logistics. Catering is comparison scenario.', 'Backup recording: storyboard included; video file must be manually recorded before the official deadline.', '', 'Files:')
$lines += ($files | Sort-Object FullName | ForEach-Object { $_.FullName.Substring($root.Length + 1) })
$lines | Set-Content -LiteralPath $manifest -Encoding UTF8
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -LiteralPath $root -DestinationPath $zip -CompressionLevel Optimal
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($zip)
$names = @($archive.Entries | ForEach-Object { $_.FullName })
$archive.Dispose()
$bad = @($names | Where-Object { $_ -match '\.env\.local($|/)' -or $_ -match '__pycache__' -or $_ -match '\.pyc$' -or $_ -match 'app\.py\.bak' })
if ($bad.Count -gt 0) { Write-Error ('Forbidden entries: ' + ($bad -join ', ')); exit 1 }
Write-Host "Created: $zip"
Write-Host ("Entries: {0}; SizeMB: {1}" -f $names.Count, [math]::Round((Get-Item $zip).Length / 1MB, 2))
Write-Host 'Archive self-check: PASS'
