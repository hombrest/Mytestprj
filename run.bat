@echo off
echo ========================================
echo FIXED .BAT EXECUTION - Starting now...
echo ========================================
set "XLSM_FILE=d:\Projects\Python\VBA\TestApp.xlsm"
cscript //nologo run_commands_v2.vbs %1 %2
pause