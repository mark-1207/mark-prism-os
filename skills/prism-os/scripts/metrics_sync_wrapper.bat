@echo off
set LOGFILE=D:\myproject\PRISM-OSv1\logs\metrics_sync.log
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONPATH=D:\myproject\PRISM-OSv1\skills\prism-os\scripts
echo === %date% %time% start === >> %LOGFILE%
cd /d D:\myproject\PRISM-OSv1\skills\prism-os\scripts
python prism_os.py metrics sync >> %LOGFILE% 2>&1
echo === sync done === >> %LOGFILE%
python prism_os.py metrics score >> %LOGFILE% 2>&1
echo === score done === >> %LOGFILE%
echo. >> %LOGFILE%
