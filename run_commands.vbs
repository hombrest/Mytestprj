' run_commands.vbs - TEST END TIME MESSAGE - NO GOTO ERRORS
Option Explicit
Dim args, durationMin, numIterations
Dim startTime, endTime, iterationCount
Dim totalDurationMin, iterationEndTime
Dim firstCmd, secondCmd, thirdCmd, scriptDir

Set args = WScript.Arguments
If args.Count < 2 Then
    WScript.Echo "Usage: cscript run_commands.vbs [duration_min] [iterations]"
    WScript.Quit 1
End If

durationMin = CLng(args(0))
numIterations = CLng(args(1))

scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

firstCmd = scriptDir & "\start_script.bat"
secondCmd = scriptDir & "\loop_script.bat"
thirdCmd = scriptDir & "\end_script.bat"

WScript.Echo "DEBUG - .BAT Paths:"
WScript.Echo "  START: " & firstCmd
WScript.Echo "  LOOP:  " & secondCmd
WScript.Echo "  END:   " & thirdCmd
WScript.Echo ""

startTime = Now()
totalDurationMin = durationMin * numIterations
endTime = DateAdd("n", totalDurationMin, startTime)

WScript.Echo "============================================"
WScript.Echo "Started: " & FormatDateTime(startTime, 3)
WScript.Echo numIterations & " iterations of " & durationMin & " min"
WScript.Echo "**LOOP EVERY 10 SECONDS - SINGLE CONSOLE**"
WScript.Echo "TEST END TIME: " & FormatDateTime(endTime, 3)
WScript.Echo "============================================"
WScript.Echo ""

iterationCount = 0

Do While iterationCount < numIterations
    iterationCount = iterationCount + 1
    
    ' FORCE TEST END TIME CHECK
    If Now() >= endTime Then
        WScript.Echo ""
        WScript.Echo "[" & FormatDateTime(Now(), 3) & "] *** TEST END TIME REACHED! EXITING. ***"
        iterationCount = numIterations ' Force exit
    Else
        WScript.Echo ""
        WScript.Echo "[" & FormatDateTime(Now(), 3) & "] === Iteration " & iterationCount & " START ==="
        
        WScript.Echo "[" & FormatDateTime(Now(), 3) & "] EXECUTING: " & firstCmd
        RunCmdWithOutput firstCmd
        
        iterationEndTime = DateAdd("n", durationMin, Now())
        
        Do While Now() < iterationEndTime
            ' FORCE TEST END TIME CHECK IN LOOP
            If Now() >= endTime Then
                WScript.Echo ""
                WScript.Echo "[" & FormatDateTime(Now(), 3) & "] *** TEST END TIME REACHED MID-LOOP! EXITING. ***"
                iterationCount = numIterations ' Force exit
                Exit Do
            End If
            
            WScript.Echo "[" & FormatDateTime(Now(), 3) & "] EXECUTING: " & secondCmd
            RunCmdWithOutput secondCmd
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

Sub RunCmdWithOutput(cmd)
    Dim shell, tempFile, fso, file, line
    Set shell = CreateObject("WScript.Shell")
    Set fso = CreateObject("Scripting.FileSystemObject")
    
    tempFile = scriptDir & "\temp_output.txt"
    
    shell.Run "cmd /c chcp 65001 >nul && cd /d """ & scriptDir & """ && """ & cmd & """ > """ & tempFile & """ 2>&1", 0, True
    
    If fso.FileExists(tempFile) Then
        Set file = fso.OpenTextFile(tempFile, 1)
        Do While Not file.AtEndOfStream
            line = file.ReadLine
            If line <> "" Then WScript.Echo "    " & line
        Loop
        file.Close
        fso.DeleteFile tempFile
    End If
End Sub