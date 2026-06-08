@echo off
setlocal enabledelayedexpansion
set LOG_DIR=D:\myproject\PRISM-OSv1\.claude\logs
set LOG_FILE=%LOG_DIR%\cron_assassin.log
set MAX_SIZE=1048576
set MAX_ROTATION=7

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: 日志轮转：超过1MB则轮转
if exist "%LOG_FILE%" (
    for %%A in ("%LOG_FILE%") do set size=%%~zA
    if !size! gtr %MAX_SIZE% (
        for /L %%i in (%MAX_ROTATION%,-1,1) do (
            set /a prev=%%i-1
            if exist "%LOG_FILE%.!prev!" move /Y "%LOG_FILE%.!prev!" "%LOG_FILE%.%%i" >nul 2>&1
        )
        move /Y "%LOG_FILE%" "%LOG_FILE%.1" >nul 2>&1
    )
)

:: 删除超过7天的旧日志
forfiles /P "%LOG_DIR%" /M "cron_assassin.log.*" /D -7 /C "cmd /c del @file" >nul 2>&1

cd /d D:\myproject\PRISM-OSv1\skills\prism-os\scripts
python assassin.py cron_check >> "%LOG_FILE%" 2>&1
