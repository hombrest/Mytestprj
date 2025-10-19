' run_commands.vbs - FINDS OPEN WORKBOOK 100%!
Option Explicit
Dim args, durationMin, numIterations
Dim startTime, endTime, iterationCount
Dim totalDurationMin, iterationEndTime
Dim firstCmd, secondCmd, thirdCmd, scriptDir
Dim xlsmFile, macroName, paramValue, moduleName
Dim shell, fso
Dim envShell, envModule

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

' FIXED: READ EXCEL_FILE DIRECTLY
xlsmFile = shell.Environment("PROCESS")("EXCEL_FILE")
If xlsmFile = "" Then
    WScript.Echo "❌ ERROR: EXCEL_FILE not defined!"
    WScript.Quit 1
End If

' Strip quotes
If Left(xlsmFile, 1) = """" Then xlsmFile = Mid(xlsmFile, 2)
If Right(xlsmFile, 1) = """" Then xlsmFile = Left(xlsmFile, Len(xlsmFile) - 1)

' AUTO-DETECT MODULE
Set envShell = CreateObject("WScript.Shell")
envModule = envShell.Environment("PROCESS")("EXCEL_MODULE")
If envModule <> "" Then
    moduleName = fso.GetBaseName(envModule)
    WScript.Echo "🔍 AUTO-DETECTED MODULE: " & moduleName
Else
    moduleName = "Module1"
End If

macroName = "CheckStatus"
paramValue = "HelloWorld"

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
firstCmd = scriptDir & "\start_script.bat"
secondCmd = scriptDir & "\loop_script.bat"
thirdCmd = scriptDir & "\end_script.bat"

WScript.Echo "DEBUG - Paths:"
WScript.Echo "  EXCEL_FILE: " & xlsmFile
WScript.Echo "  WORKBOOK: " & fso.GetFileName(xlsmFile)
WScript.Echo "  MODULE: " & moduleName & "." & macroName & "( """ & paramValue & """ )"
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
            WScript.Sleep 10000
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
    Dim xlApp, wb, result
    Err.Clear
    
    ' ULTIMATE FIX: GET EXISTING EXCEL + ACTIVE WORKBOOK!
    WScript.Echo "    [SINGLE] Connecting to existing Excel..."
    
    Set xlApp = GetObject(, "Excel.Application")
    If Err.Number <> 0 Then
        WScript.Echo "    [ERROR] No Excel running!"
        RunVbaFunction = "ERROR: No Excel"
        Exit Function
    End If
    Err.Clear
    
    ' USE ACTIVE WORKBOOK (from import!)
    Set wb = xlApp.ActiveWorkbook
    If wb Is Nothing Then
        WScript.Echo "    [ERROR] No active workbook!"
        RunVbaFunction = "ERROR: No active"
        Exit Function
    End If
    
    wb.Activate
    xlApp.Visible = True
    WScript.Echo "    [REUSED] Active: " & wb.Name
    
    ' RUN FUNCTION
    WScript.Echo "    [RUN] " & modName & "." & funcName & "( """ & paramValue & """ )"
    result = wb.Application.Run(modName & "." & funcName, """" & paramValue & """")
    
    If Err.Number = 0 Then
        WScript.Echo "    [SUCCESS] " & result
        RunVbaFunction = result
    Else
        WScript.Echo "    [ERROR] " & Err.Number & ": " & CleanError(Err.Description)
        RunVbaFunction = "ERROR: " & Err.Number
        Err.Clear
    End If
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