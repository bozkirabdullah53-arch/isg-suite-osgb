# ISG Suite Signer kurulum — yönetici GEREKTIRMEZ.
# IBYSIS HSNSigner (port 16999) ile ÇAKIŞMAZ; bu servis 17000 kullanır.
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Hedef = Join-Path $env:LOCALAPPDATA "ISGSuiteSigner"
New-Item -ItemType Directory -Force -Path $Hedef | Out-Null

Write-Host "OSGB Signer kuruluyor..." -ForegroundColor Cyan

# Python bul
$py = $null
foreach ($c in @("py -3", "python", "python3")) {
  try {
    $ver = & cmd /c "$c --version 2>&1"
    if ($LASTEXITCODE -eq 0 -and $ver -match "Python 3") { $py = $c; break }
  } catch {}
}
if (-not $py) {
  Write-Host "Python 3 bulunamadı. https://www.python.org/downloads/ adresinden kurun (Add to PATH)." -ForegroundColor Red
  exit 1
}

$venv = Join-Path $Hedef "venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
  Write-Host "Sanal ortam oluşturuluyor..."
  cmd /c "$py -m venv `"$venv`""
  if ($LASTEXITCODE -ne 0) { throw "venv oluşturulamadı" }
}
$pip = Join-Path $venv "Scripts\pip.exe"
$python = Join-Path $venv "Scripts\python.exe"

Write-Host "Bağımlılıklar kuruluyor..."
& $pip install --upgrade pip | Out-Null
& $pip install -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install başarısız" }

# Agent kaynaklarını kopyala
$agentDst = Join-Path $Hedef "agent"
if (Test-Path $agentDst) { Remove-Item $agentDst -Recurse -Force }
Copy-Item -Recurse (Join-Path $Root "agent") $agentDst
Copy-Item -Force (Join-Path $Root "requirements.txt") $Hedef
Copy-Item -Force (Join-Path $Root "BENIOKU.txt") $Hedef -ErrorAction SilentlyContinue

# Sertifikalar + config
$pwTls = [Guid]::NewGuid().ToString("N")
$pwDemo = [Guid]::NewGuid().ToString("N")
$tlsPfx = Join-Path $Hedef "localhost.pfx"
$demoPfx = Join-Path $Hedef "demo-signer.pfx"

$env:ISG_SIGNER_HOME = $Hedef
Push-Location $Hedef
try {
  & $python -c @"
from pathlib import Path
import os
from agent.signing import ensure_localhost_tls, ensure_demo_signing_cert
from agent.config import DEFAULT_ORIGINS, DEFAULT_PORT, save_config
home = Path(os.environ['ISG_SIGNER_HOME'])
ensure_localhost_tls(home / 'localhost.pfx', '$pwTls')
ensure_demo_signing_cert(home / 'demo-signer.pfx', '$pwDemo')
save_config({
  'ListenPort': DEFAULT_PORT,
  'AllowedOrigins': list(DEFAULT_ORIGINS),
  'Tls': {'Enabled': True, 'CertificatePath': str(home / 'localhost.pfx'), 'CertificatePassword': '$pwTls'},
  'Signing': {
    'DemoCertPath': str(home / 'demo-signer.pfx'),
    'DemoCertPassword': '$pwDemo',
    'UserCertPath': '',
    'UserCertPassword': '',
    'Pkcs11Module': '',
  },
  'RequestSizeLimitBytes': 41943040,
})
print('config ok')
"@
  if ($LASTEXITCODE -ne 0) { throw "sertifika/config oluşturulamadı" }
} finally { Pop-Location }

# TLS sertifikasını kullanıcı Root deposuna ekle (admin gerekmez)
try {
  $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($tlsPfx, $pwTls)
  $store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
  $store.Open("ReadWrite")
  $store.Add($cert)
  $store.Close()
  Write-Host "HTTPS localhost sertifikası güvenilir olarak eklendi." -ForegroundColor Green
} catch {
  Write-Host "Uyarı: Root deposuna eklenemedi ($($_.Exception.Message)). Tarayıcı uyarısı çıkabilir." -ForegroundColor Yellow
}

# Başlatıcı
$runner = Join-Path $Hedef "BASLAT.cmd"
@"
@echo off
set ISG_SIGNER_HOME=$Hedef
cd /d "$Hedef"
"$python" -m agent
"@ | Set-Content -Path $runner -Encoding ASCII

# Startup kısayolu
$lnk = Join-Path ([Environment]::GetFolderPath("Startup")) "ISGSuiteSigner.lnk"
$sc = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$sc.TargetPath = $runner
$sc.WorkingDirectory = $Hedef
$sc.WindowStyle = 7
$sc.Save()

# Çalışan eski süreci nazikçe atla; yeniden başlat
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -match "ISGSuiteSigner" -and $_.CommandLine -match "-m agent" } |
  ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }

Start-Process -FilePath $runner -WorkingDirectory $Hedef -WindowStyle Hidden
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "Kuruldu. ISG Suite Signer arka planda calisiyor (port 17000)." -ForegroundColor Green
Write-Host "Kontrol: https://127.0.0.1:17000/health" -ForegroundColor Green
Write-Host "www.isgsuite.tr Belge Onay ekraninda 'Yerel imza köprüsü' durumunu görün." -ForegroundColor Green
Write-Host "IBYSIS HSNSigner (16999) varsa bozulmaz; ayrı port." -ForegroundColor DarkGray
