$logFile = "$env:TEMP\tunnel_url.txt"
$backendDir = "C:\Users\Mbarek\Desktop\opencode\saas-vinted\backend"

# Kill old processes
Get-Process -Name "ssh" -ErrorAction SilentlyContinue | Stop-Process -Force
$pids = netstat -ano | Select-String ":8001 " | ForEach-Object { $_.ToString() -split '\s+' | Where-Object { $_ -match '^\d+$' } } | Select-Object -Unique
foreach ($p in $pids) { if ($p -and $p -ne 0) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } }
Start-Sleep -Seconds 2

# Start backend
$python = Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port 8001" -WorkingDirectory $backendDir -PassThru
Write-Host "[1/3] Backend démarré" -ForegroundColor Green

Start-Sleep -Seconds 3

# Start tunnel and capture URL
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "ssh"
$psi.Arguments = "-o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 80:localhost:8001 nokey@localhost.run"
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$p = [System.Diagnostics.Process]::Start($psi)

Start-Sleep -Seconds 8

# Read the output
$out = $p.StandardOutput.ReadToEnd()
$err = $p.StandardError.ReadToEnd()
$all = $out + $err

# Extract URL
$url = ""
if ($all -match 'https://([a-zA-Z0-9-]+\.lhr\.life)') {
    $url = $matches[0]
}

Set-Content -Path $logFile -Value $url
Write-Host "[2/3] Tunnel actif: $url" -ForegroundColor Green

# Verify
try {
    $r = Invoke-WebRequest -Uri "$url/api/health" -UseBasicParsing -TimeoutSec 10
    Write-Host "[3/3] Backend accessible via tunnel!" -ForegroundColor Green
} catch {
    Write-Host "[3/3] Attente du tunnel..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}

Write-Host ""
Write-Host "URL du backend: $url" -ForegroundColor Cyan
Write-Host "Mets cette URL dans frontend/config.js" -ForegroundColor Cyan
Write-Host ""

# Keep running
while ($true) { Start-Sleep -Seconds 10 }
