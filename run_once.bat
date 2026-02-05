@echo off
chcp 65001 >nul
REM ============================================================
REM  手動執行一次爬蟲，將資料寫入 F:\OPTCG\scraped_data.db
REM ============================================================

set SCRIPT_DIR=%~dp0
set PYTHON_EXE=%SCRIPT_DIR%venv\Scripts\python.exe
set URL=https://yuyu-tei.jp/top/opc
set DB_PATH=F:\OPTCG\scraped_data.db

REM 確保 DB 目錄存在
if not exist "F:\OPTCG\" mkdir "F:\OPTCG"

echo [INFO] 開始執行爬蟲...
"%PYTHON_EXE%" "%SCRIPT_DIR%main.py" --url "%URL%" --db "%DB_PATH%"

if %ERRORLEVEL% equ 0 (
    echo.
    echo [OK] 爬蟲執行完成。
) else (
    echo.
    echo [ERROR] 爬蟲執行失敗，錯誤碼: %ERRORLEVEL%
)

pause
