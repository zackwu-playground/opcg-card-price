@echo off
REM ============================================================
REM  建立 Windows 排程工作：每天 20:00 執行爬蟲
REM  使用方式：以系統管理員身份執行此 bat 檔
REM ============================================================

set TASK_NAME=OPCG_Daily_Scrape
set SCRIPT_DIR=%~dp0
set PYTHON_EXE=python
set URL=https://yuyu-tei.jp/top/opc
set DB_PATH=F:\OPTCG\scraped_data.db

REM 刪除舊的同名排程（若存在）
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

REM 建立每日 20:00 執行的排程工作
schtasks /Create ^
    /TN "%TASK_NAME%" ^
    /TR "\"%PYTHON_EXE%\" \"%SCRIPT_DIR%main.py\" --url \"%URL%\" --db \"%DB_PATH%\"" ^
    /SC DAILY ^
    /ST 20:00 ^
    /RL HIGHEST ^
    /F

if %ERRORLEVEL% equ 0 (
    echo.
    echo [OK] 排程工作 "%TASK_NAME%" 已建立，每天 20:00 執行。
    echo      可透過「工作排程器」或以下指令確認：
    echo      schtasks /Query /TN "%TASK_NAME%"
) else (
    echo.
    echo [ERROR] 建立排程失敗，請確認以系統管理員身份執行。
)

pause
