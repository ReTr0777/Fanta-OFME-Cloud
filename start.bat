@echo off
title Fanta-OFME-Cloud Server
echo ============================================================
echo   Starting Fanta-OFME-Cloud Save Sync Server...
echo ============================================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else if exist "..\Simple-OFME-Downloader-LIB\.venv\Scripts\python.exe" (
    "..\Simple-OFME-Downloader-LIB\.venv\Scripts\python.exe" app.py
) else (
    python app.py
)
pause

