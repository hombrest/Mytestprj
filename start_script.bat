@echo off
echo.
echo [%TIME%] ★★★ START_SCRIPT.BAT EXECUTED ★★★
echo [%TIME%] This is iteration START command!
timeout /t 2 >nul
echo [%TIME%] Start script COMPLETE.
set /a MyVar = Myvar + 1
echo MyVar: %MyVar%