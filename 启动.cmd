@echo off
chcp 65001 >nul
title Delivery Contract Desk
echo.
echo   ==========================================
echo    Delivery Contract Desk  (FDE)
echo   ==========================================
echo.
echo   Double-click again is safe - it will NOT
echo   start a second server (idempotent).
echo.
echo   Closing this window does NOT stop the
echo   server. Open http://127.0.0.1:8501 anytime.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-app.ps1" %*
echo.
echo   Done. You can close this window.
pause >nul
