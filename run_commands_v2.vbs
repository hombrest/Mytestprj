' run_commands.vbs - YOUR EXACT FIX: """" & paramValue & """"
Option Explicit
Dim args, durationMin, numIterations
Dim startTime, endTime, iterationCount
Dim totalDurationMin, iterationEndTime
Dim firstCmd, secondCmd, thirdCmd, scriptDir
Dim xlsmFile, macroName, paramValue, moduleName
Dim shell, fso  ' Global objects

Set args = WScript.Arguments
If args.Count < 2 Then
    WScript.Echo "Usage: cscript run_commands.vbs [duration_min] [iterations]"
    WScript.Quit 1
End If

durationMin = CLng(args(0))
numIterations = CLng(args(1))

' Initialize globals
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get XLSM_FILE and STRIP QUOTES
xlsmFile = shell.Environment("PROCESS")("XLSM_FILE")
If Left(xlsmFile, 1) = """" Then xlsmFile = Mid(xlsmFile, 2)
If Right(xlsmFile, 1) = """" Then xlsmFile = Left(xlsmFile, Len(xlsmFile) - 1)

' ============================================
' **CHANGE ONLY LINE 30 FOR YOUR PARAMETER!**
' ============================================
moduleName = "Module1"        ' Your module name
macroName = "CheckStatus"     ' Your function name
paramValue = "HelloWorld"     ' Your parameter (NO quotes needed!)
' ============================================

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

firstCmd = scriptDir & "\start_script.bat"
secondCmd = scriptDir & "\loop_script.bat"
thirdCmd = scriptDir & "\end_script.bat"

WScript.Echo "DEBUG - Paths:"
WScript.Echo "  START: " & firstCmd
WScript.Echo "  LOOP:  " & secondCmd
WScript.Echo "  END:   " & thirdCmd
WScript.Echo "  XLSM PATH: " & xlsmFile
WScript.Echo "  WORKBOOK NAME: " & fso.GetFileName(xlsmFile)
WScript.Echo "  FUNCTION: " & moduleName & "." & macroName & "( """ & paramValue & """ )"
WScript.Echo ""

startTime = Now()
totalDurationMin = durationMin * numIterations
endTime = DateAdd("n", totalDurationMin, startTime)

WScript.Echo "============================================"
WScript.Echo "Started: " & FormatDateTime(startTime, 3)
WScript.Echo numIterations & " iterations of " & durationMin & " min"
WScript.Echo "**LOOP EVERY 10 SECONDS - " & moduleName & "." & macroName & " **"
WScript.Echo "TEST END TIME: " & FormatDateTime(endTime, 3)
WScript.Echo "============================================"
WScript.Echo ""

iterationCount = 0

Do While iterationCount < numIterations
    iterationCount = iterationCount + 1
    
    If Now() >= endTime Then
        WScript.Echo ""
        WScript.Echo "[" & FormatDateTime(Now(), 3) & "] *** TEST END TIME REACHED! EXITING. ***"
        iterationCount = numIterations
    Else
        WScript.Echo ""
        WScript.Echo "[" & FormatDateTime(Now(), 3) & "] === Iteration " & iterationCount & " START ==="
        
        WScript.Echo "[" & FormatDateTime(Now(), 3) & "] EXECUTING: " & firstCmd
        RunCmdWithOutput firstCmd
        
        iterationEndTime = DateAdd("n", durationMin, Now())
        
        Do While Now() < iterationEndTime
            If Now() >= endTime Then
                WScript.Echo ""
                WScript.Echo "[" & FormatDateTime(Now(), 3) & "] *** TEST END TIME REACHED MID-LOOP! EXITING. ***"
                iterationCount = numIterations
                Exit Do
            End If
            
            WScript.Echo "[" & FormatDateTime(Now(), 3) & "] EXECUTING: " & secondCmd
            RunCmdWithOutput secondCmd
            
            WScript.Echo "[" & FormatDateTime(Now(), 3) & "] CALLING " & moduleName & "." & macroName & "( """ & paramValue & """ )"
            Dim returnValue
            returnValue = RunVbaFunction(xlsmFile, moduleName, macroName, paramValue)
            WScript.Sleep 5000
        Loop
        
        WScript.Echo "[" & FormatDateTime(Now(), 3) & "] EXECUTING: " & thirdCmd
        RunCmdWithOutput thirdCmd
        WScript.Echo "[" & FormatDateTime(Now(), 3) & "] === Iteration " & iterationCount & " END ==="
        
        WScript.Sleep 1000
    End If
Loop

WScript.Echo ""
WScript.Echo "[" & FormatDateTime(Now(), 3) & "] COMPLETED!"

Function RunVbaFunction(filePath, modName, funcName, paramValue)
    On Error Resume Next
    Dim xlApp, wb, result, wbName
    Err.Clear
    
    Set xlApp = GetObject(, "Excel.Application")
    If Err.Number <> 0 Then
        WScript.Echo "    --- ERROR: Excel not running! ---"
        RunVbaFunction = "ERROR: Excel not running"
        Exit Function
    End If
    
    wbName = fso.GetFileName(filePath)
    Set wb = xlApp.Workbooks(wbName)
    If Err.Number <> 0 Then
        WScript.Echo "    --- ERROR: Workbook '" & wbName & "' not open! ---"
        WScript.Echo "    Expected: " & filePath
        WScript.Echo "    Open workbooks:"
        Dim i
        For i = 1 To xlApp.Workbooks.Count
            WScript.Echo "       - " & xlApp.Workbooks(i).Name
        Next
        RunVbaFunction = "ERROR: Workbook not open"
        Exit Function
    End If
    
    ' YOUR EXACT FIX: Pass """" & paramValue & """"
    WScript.Echo "    Parameter: """ & paramValue & """ (VBA string)"
    result = wb.Application.Run(modName & "." & funcName, """" & paramValue & """")
    
    If Err.Number = 0 Then
        WScript.Echo "    --- SUCCESS ---"
        WScript.Echo "    " & modName & "." & funcName & "( """ & paramValue & """ ) = " & result
        WScript.Echo "    --- SUCCESS ---"
        RunVbaFunction = result
    Else
        WScript.Echo "    --- VBA ERROR ---"
        WScript.Echo "    Function: " & modName & "." & funcName & "( """ & paramValue & """ )"
        WScript.Echo "    Error Code: " & Err.Number
        WScript.Echo "    Error Message: " & CleanError(Err.Description)
        WScript.Echo "    --- VBA ERROR ---"
        RunVbaFunction = "ERROR " & Err.Number & ": " & CleanError(Err.Description)
        Err.Clear
    End If
End Function

Function CleanError(errText)
    CleanError = Replace(Replace(Replace(errText, vbCrLf, " "), vbLf, " "), vbCr, " ")
    CleanError = Replace(CleanError, Chr(9), " ")
    CleanError = Replace(CleanError, Chr(34), "'")
End Function

Sub RunCmdWithOutput(cmd)
    Dim tempShell, tempFile, tempFso, file, line
    Set tempShell = CreateObject("WScript.Shell")
    Set tempFso = CreateObject("Scripting.FileSystemObject")
    
    tempFile = scriptDir & "\temp_output.txt"
    
    tempShell.Run "cmd /c chcp 65001 >nul && cd /d """ & scriptDir & """ && """ & cmd & """ > """ & tempFile & """ 2>&1", 0, True
    
    If tempFso.FileExists(tempFile) Then
        Set file = tempFso.OpenTextFile(tempFile, 1)
        Do While Not file.AtEndOfStream
            line = file.ReadLine
            If line <> "" Then WScript.Echo "    " & line
        Loop
        file.Close
        tempFso.DeleteFile tempFile
    End If
End Sub