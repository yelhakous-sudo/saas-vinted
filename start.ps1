param([int]$Port = 8001)

Write-Host "=== VintedPro SaaS - Analyseur de Marge ===" -ForegroundColor Cyan
Write-Host ""

$processes = netstat -ano | Select-String ":${Port} " | ForEach-Object { $_ -split '\s+' | Select-Object -Last 1 } | Select-Object -Unique
foreach ($pid in $processes) { if ($pid -and $pid -ne 0) { try { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue } catch {} } }

$backendDir = Join-Path $PSScriptRoot "backend"
Write-Host "[1/2] Démarrage du backend sur le port $Port..." -ForegroundColor Yellow
$backend = Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port $Port" -WorkingDirectory $backendDir -PassThru
Start-Sleep -Seconds 4

try {
    $r = Invoke-WebRequest -Uri "http://localhost:$Port/api/health" -UseBasicParsing -ErrorAction Stop
    Write-Host "  ✓ Backend OK - Vinted connecté" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Erreur backend: $_" -ForegroundColor Red
    exit 1
}

Write-Host "[2/2] Ouverture du dashboard..." -ForegroundColor Yellow
Start-Process "http://localhost:$Port/"

Write-Host ""
Write-Host "=== Dashboard : http://localhost:$Port/ ===" -ForegroundColor Green
Write-Host "Appuie sur Ctrl+C pour arrêter" -ForegroundColor Gray

try {
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
}
