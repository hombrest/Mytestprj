@echo off
echo ========================================
echo FIXED .BAT EXECUTION - Starting now...
echo ========================================
set "EXCEL_FILE=d:\Projects\Python\VBA\TestApp.xlsm"
set "EXCEL_MODULE=d:\Projects\Python\VBA\Module1.bas"
:: cscript //nologo import_module.vbs
start %EXCEL_FILE%
echo.
echo WAITING 5 SECONDS FOR EXCEL...
timeout /t 5 /nobreak >nul
echo.
cscript //nologo run_commands_v2.vbs %1 %2
pause