@echo off
chcp 65001 >nul
echo ISG Suite Signer kuruluyor...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0KUR.ps1"
echo.
pause
