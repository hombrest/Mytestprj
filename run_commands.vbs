Option Explicit
Dim args, durationMin, numIterations
Dim startTime, endTime, iterationCount
Dim xlsmFile, scriptDir
Dim shell, fso, logFile

' PARSE ARGUMENTS
Set args = WScript.Arguments
If args.Count < 2 Then
    WScript.Echo "Usage: cscript run_commands.vbs [duration_min] [iterations]"
    WScript.Quit 1
End If

durationMin = CLng(args(0))
numIterations = CLng(args(1))

' INITIALIZE GLOBALS
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
xlsmFile = shell.Environment("PROCESS")("EXCEL_FILE")

If xlsmFile = "" Then
    WScript.Echo "[ERROR] EXCEL_FILE not defined!"
    WScript.Quit 1
End If

' STRIP QUOTES
If Left(xlsmFile, 1) = """" Then xlsmFile = Mid(xlsmFile, 2)
If Right(xlsmFile, 1) = """" Then xlsmFile = Left(xlsmFile, Len(xlsmFile) - 1)

' SETUP CSV LOG FILE
logFile = scriptDir & "\VBA_Log_" & Replace(FormatDateTime(Now(), 3), ":", "-") & ".csv"
Set fso.CreateTextFile(logFile, True).WriteLine "Timestamp,Result,Parameter"

WScript.Echo "[LOG] Writing to: " & logFile

' START TIMING
startTime = Now()
endTime = DateAdd("n", durationMin * numIterations, startTime)

WScript.Echo "[START] " & FormatDateTime(startTime, 3)
WScript.Echo "[PLAN] " & numIterations & " iterations of " & durationMin & " min"
WScript.Echo "[END] " & FormatDateTime(endTime, 3)
WScript.Echo ""

' MAIN LOOP
iterationCount = 0
Dim lastSqlUpdate
lastSqlUpdate = Now()

Do While iterationCount < numIterations
    iterationCount = iterationCount + 1
    
    WScript.Echo "[ITERATION] " & iterationCount & " START"
    
    ' RUN START FUNCTIONS
    Dim startResults
    startResults = RunVbaFunctions(xlsmFile, "START")
    LogResults startResults, "START"
    
    ' INNER LOOP
    Dim innerResults, iterationEndTime
    iterationEndTime = DateAdd("n", durationMin, Now())
    
    Do While Now() < iterationEndTime
        If Now() >= endTime Then
            WScript.Echo "[DONE] End time reached!"
            Exit Do
        End If
        
        innerResults = RunVbaFunctions(xlsmFile, "INNER")
        LogResults innerResults, "INNER"
        
        ' SQL UPDATE EVERY MINUTE
        If DateDiff("s", lastSqlUpdate, Now()) >= 60 Then
            UpdateSqlServer innerResults
            lastSqlUpdate = Now()
        End If
        
        WScript.Sleep 10000
    Loop
    
    ' RUN END FUNCTIONS
    Dim endResults
    endResults = RunVbaFunctions(xlsmFile, "END")
    LogResults endResults, "END"
    
    WScript.Echo "[ITERATION] " & iterationCount & " END"
    
    If Now() >= endTime Then
        WScript.Echo "[DONE] Total end time reached!"
        Exit Do
    End If
Loop

WScript.Echo "[COMPLETED] " & FormatDateTime(Now(), 3)
MsgBox "Execution complete! Log: " & logFile, vbInformation, "DONE"

Function RunVbaFunctions(filePath, phase)
    On Error Resume Next
    Dim xlApp, wb, result, results, functions, i
    Err.Clear
    
    ' CONNECT TO EXCEL
    WScript.Echo "    [" & phase & "] Connecting to Excel..."
    Set xlApp = GetObject(, "Excel.Application")
    If Err.Number <> 0 Then
        WScript.Echo "    [ERROR] No Excel running! Opening: " & filePath
        Set xlApp = CreateObject("Excel.Application")
        xlApp.Visible = True
        Set wb = xlApp.Workbooks.Open(filePath)
        wb.Activate
    Else
        Set wb = xlApp.ActiveWorkbook
        wb.Activate
        WScript.Echo "    [REUSED] " & wb.Name
    End If
    
    ' DEFINE FUNCTIONS (ASSUME DOUBLE OUTPUT)
    If phase = "START" Then
        functions = Array( _
            Array("Module1", "InitSession", "Start1"), _
            Array("Module1", "SetupConfig", "ConfigA") _
        )
    ElseIf phase = "END" Then
        functions = Array( _
            Array("Module1", "CleanupSession", "End1"), _
            Array("Module1", "LogSummary", "SummaryA") _
        )
    Else ' INNER
        functions = Array( _
            Array("Module1", "CheckStatus", "HelloWorld"), _
            Array("Module1", "GetVersion", "App1"), _
            Array("Module1", "ProcessData", "TestInput") _
        )
    End If
    
    ReDim results(UBound(functions))
    
    For i = 0 To UBound(functions)
        WScript.Echo "    [" & phase & "] " & functions(i)(0) & "." & functions(i)(1) & "( """ & functions(i)(2) & """ )"
        result = wb.Application.Run(functions(i)(0) & "." & functions(i)(1), """" & functions(i)(2) & """")
        
        If Err.Number = 0 Then
            results(i) = Array(Now(), CDbl(result), functions(i)(2))
            WScript.Echo "    [SUCCESS] " & result
        Else
            results(i) = Array(Now(), -1, functions(i)(2) & " ERROR: " & Err.Number)
            WScript.Echo "    [ERROR] " & Err.Number & ": " & CleanError(Err.Description)
            Err.Clear
        End If
    Next
    
    RunVbaFunctions = results
End Function

Sub LogResults(results, phase)
    Dim file, i
    Set file = fso.OpenTextFile(logFile, 8, True)
    For i = 0 To UBound(results)
        file.WriteLine """" & FormatDateTime(results(i)(0), 3) & """," & results(i)(1) & ",""" & results(i)(2) & """"
    Next
    file.Close
End Sub

Sub UpdateSqlServer(results)
    On Error Resume Next
    Dim conn, cmd, i, jobStatus, ipAddress
    
    ' GET IP ADDRESS
    ipAddress = GetIPAddress()
    If ipAddress = "" Then
        ipAddress = "UNKNOWN"
    End If
    
    ' DETERMINE JOB STATUS
    jobStatus = "SUCCESS"
    For i = 0 To UBound(results)
        If results(i)(1) = -1 Then
            jobStatus = "ERROR"
            Exit For
        End If
    Next
    
    ' CALL STORED PROCEDURE
    Set conn = CreateObject("ADODB.Connection")
    conn.ConnectionString = "Provider=SQLOLEDB;Server=YOUR_SERVER;Database=YOUR_DB;Trusted_Connection=Yes;"
    conn.Open
    
    If Err.Number <> 0 Then
        WScript.Echo "[SQL ERROR] Cannot connect: " & Err.Description
        LogResults Array(Array(Now(), -1, "SQL ERROR: " & Err.Description)), "SQL"
        Exit Sub
    End If
    
    Set cmd = CreateObject("ADODB.Command")
    cmd.ActiveConnection = conn
    cmd.CommandType = 4 ' adCmdStoredProc
    cmd.CommandText = "UpdateVbaJobStatus"
    
    cmd.Parameters.Append cmd.CreateParameter("@IPAddress", 200, 1, 50, ipAddress)
    cmd.Parameters.Append cmd.CreateParameter("@JobStatus", 200, 1, 50, jobStatus)
    
    cmd.Execute
    
    If Err.Number <> 0 Then
        WScript.Echo "[SQL ERROR] Stored proc failed: " & Err.Description
        LogResults Array(Array(Now(), -1, "SQL ERROR: " & Err.Description)), "SQL"
    Else
        WScript.Echo "[SQL] Stored proc called at " & FormatDateTime(Now(), 3) & ": IP=" & ipAddress & ", Status=" & jobStatus
    End If
    
    conn.Close
End Sub

Function GetIPAddress()
    On Error Resume Next
    Dim wmi, colItems, objItem
    Set wmi = GetObject("winmgmts://./root/cimv2")
    Set colItems = wmi.ExecQuery("SELECT * FROM Win32_NetworkAdapterConfiguration WHERE IPEnabled = True")
    For Each objItem In colItems
        If Not IsNull(objItem.IPAddress) Then
            GetIPAddress = objItem.IPAddress(0)
            Exit Function
        End If
    Next
    GetIPAddress = ""
End Function

Function CleanError(errText)
    CleanError = Replace(Replace(Replace(errText, vbCrLf, " "), vbLf, " "), vbCr, " ")
    CleanError = Replace(CleanError, Chr(9), " ")
    CleanError = Replace(CleanError, Chr(34), "'")
End Function