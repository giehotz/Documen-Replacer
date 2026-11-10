@echo off
title Smart RPP Replacer
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ======================================================
    echo        SMART RPP REPLACER - KOMPONEN BELUM ADA
    echo ======================================================
    echo Python tidak ditemukan di sistem ini.
    echo Silakan unduh dan pasang Python dari: https://www.python.org/
    echo Pastikan mencentang "Add Python to PATH" saat instalasi.
    echo ======================================================
    echo.
    pause
    exit /b 1
)

where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw main.py
) else (
    python main.py
)
