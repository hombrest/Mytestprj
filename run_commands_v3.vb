Option Explicit
Dim durationMin, numIterations
Dim startTime, endTime, iterationCount
Dim xlsmFile, scriptDir, xlApp, wb
Dim shell, fso, logFile
Dim secondDurationSec, secondNumIterations, secondIterationCount, secondNextRun
Dim startFunctions, innerFunctions, endFunctions, secondEndFunctions
Dim shouldStop ' Flag for control table

' INITIALIZE GLOBALS
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
xlsmFile = shell.Environment("PROCESS")("EXCEL_FILE")
shouldStop = False ' Initialize stop flag

If xlsmFile = "" Then
    WScript.Echo "[ERROR] EXCEL_FILE not defined!"
    WScript.Quit 1
End If

' STRIP QUOTES
If Left(xlsmFile, 1) = """" Then xlsmFile = Mid(xlsmFile, 2)
If Right(xlsmFile, 1) = """" Then xlsmFile = Left(xlsmFile, Len(xlsmFile) - 1)

' SETUP CSV LOG
logFile = scriptDir & "\VBA_Log_" & Replace(FormatDateTime(Now(), 3), ":", "-") & ".csv"
Set fso.CreateTextFile(logFile, True).WriteLine "Timestamp,Result,Parameter"

WScript.Echo "[LOG] Writing to: " & logFile

' LOAD CONFIG FROM SQL
WScript.Echo "[SQL] Loading configuration from database..."
LoadConfig

' LOAD VBA FUNCTIONS FROM SQL
WScript.Echo "[SQL] Loading VBA functions from database..."
LoadVbaFunctions

' INITIALIZE EXCEL ONCE
Set xlApp = Nothing
WScript.Echo "[OPEN] Connecting to Excel..."
On Error Resume Next
Set xlApp = GetObject(, "Excel.Application")
If Err.Number <> 0 Then
    WScript.Echo "    [OPEN] No Excel running! Opening: " & xlsmFile
    Set xlApp = CreateObject("Excel.Application")
    xlApp.Visible = True
    Set wb = xlApp.Workbooks.Open(xlsmFile)
    wb.Activate
Else
    Set wb = xlApp.ActiveWorkbook
    wb.Activate
    WScript.Echo "    [REUSED] " & wb.Name
End If
Err.Clear
On Error GoTo 0

If wb Is Nothing Then
    WScript.Echo "[FATAL] Cannot open workbook!"
    WScript.Quit 1
End If

' START TIMING
startTime = Now()
endTime = DateAdd("n", durationMin * numIterations, startTime)

WScript.Echo "[START] " & FormatDateTime(startTime, 3)
WScript.Echo "[MAIN LOOP] " & numIterations & " iterations of " & durationMin & " min"
WScript.Echo "[SECOND LOOP] " & secondNumIterations & " iterations of " & secondDurationSec & " sec"
WScript.Echo "[MAIN END] " & FormatDateTime(endTime, 3)
WScript.Echo "[SECOND END] " & FormatDateTime(DateAdd("s", secondDurationSec * secondNumIterations, startTime), 3)
WScript.Echo ""

' MAIN LOOP
iterationCount = 0
secondIterationCount = 0
secondNextRun = startTime
Dim lastSqlUpdate
lastSqlUpdate = Now()

Do While iterationCount < numIterations
    iterationCount = iterationCount + 1
    WScript.Echo "[MAIN ITERATION] " & iterationCount & " START"
    
    ' RUN START FUNCTIONS
    Dim startResults
    startResults = RunVbaFunctions("START")
    LogResults startResults, "START"
    
    ' INNER LOOP (HIGH-FREQUENCY)
    Dim innerResults, iterationEndTime
    iterationEndTime = DateAdd("n", durationMin, Now())
    
    Do While Now() < iterationEndTime
        If Now() >= endTime Or shouldStop Then
            WScript.Echo "[DONE] Main end time reached or stop signaled!"
            Exit Do
        End If
        
        ' CHECK SECOND LOOP
        If secondIterationCount < secondNumIterations And Now() >= secondNextRun Then
            secondIterationCount = secondIterationCount + 1
            WScript.Echo "[SECOND ITERATION] " & secondIterationCount & " START"
            
            ' RUN SECOND LOOP END FUNCTIONS
            Dim secondEndResults
            secondEndResults = RunVbaFunctions("SECOND_END")
            LogResults secondEndResults, "SECOND_END"
            
            WScript.Echo "[SECOND ITERATION] " & secondIterationCount & " END"
            secondNextRun = DateAdd("s", secondDurationSec, secondNextRun)
        End If
        
        innerResults = RunVbaFunctions("INNER")
        LogResults innerResults, "INNER"
        
        ' SQL UPDATE EVERY MINUTE
        If DateDiff("s", lastSqlUpdate, Now()) >= 60 Then
            UpdateSqlServer innerResults
            lastSqlUpdate = Now()
            If shouldStop Then
                WScript.Echo "[CONTROL] Stop signaled by VbaControl table!"
                Exit Do
            End If
        End If
        
        WScript.Sleep 5000
    Loop
    
    ' RUN MAIN LOOP END FUNCTIONS
    Dim endResults
    endResults = RunVbaFunctions("END")
    LogResults endResults, "END"
    
    WScript.Echo "[MAIN ITERATION] " & iterationCount & " END"
    
    If Now() >= endTime Or shouldStop Then
        WScript.Echo "[DONE] Total main end time reached or stop signaled!"
        Exit Do
    End If
Loop

WScript.Echo "[COMPLETED] " & FormatDateTime(Now(), 3)
xlApp.Quit
MsgBox "Execution complete! Log: " & logFile, vbInformation, "DONE"

Sub LoadConfig()
    On Error Resume Next
    Dim conn, rs
    Set conn = CreateObject("ADODB.Connection")
    conn.ConnectionString = "Provider=SQLOLEDB;Server=YOUR_SERVER;Database=YOUR_DB;Trusted_Connection=Yes;"
    conn.Open
    
    If Err.Number <> 0 Then
        WScript.Echo "[SQL ERROR] Cannot connect to load config: " & Err.Description
        WScript.Quit 1
    End If
    
    Set rs = CreateObject("ADODB.Recordset")
    rs.Open "SELECT ConfigKey, ConfigValue FROM VbaConfig", conn
    
    If Err.Number <> 0 Then
        WScript.Echo "[SQL ERROR] Cannot query config: " & Err.Description
        conn.Close
        WScript.Quit 1
    End If
    
    ' DEFAULT VALUES
    durationMin = 1
    numIterations = 4
    secondDurationSec = 90
    secondNumIterations = 2
    
    Do Until rs.EOF
        Dim key, value
        key = rs("ConfigKey").Value
        value = CLng(rs("ConfigValue").Value)
        
        If key = "MainDurationMin" Then
            durationMin = value
        ElseIf key = "MainIterations" Then
            numIterations = value
        ElseIf key = "SecondDurationSec" Then
            secondDurationSec = value
        ElseIf key = "SecondIterations" Then
            secondNumIterations = value
        End If
        
        rs.MoveNext
    Loop
    
    rs.Close
    conn.Close
    
    WScript.Echo "[SQL] Loaded config: MainDurationMin=" & durationMin & ", MainIterations=" & numIterations & ", SecondDurationSec=" & secondDurationSec & ", SecondIterations=" & secondNumIterations
End Sub

Sub LoadVbaFunctions()
    On Error Resume Next
    Dim conn, rs, phase, moduleName, functionName, parameter, tempArray
    Set conn = CreateObject("ADODB.Connection")
    conn.ConnectionString = "Provider=SQLOLEDB;Server=YOUR_SERVER;Database=YOUR_DB;Trusted_Connection=Yes;"
    conn.Open
    
    If Err.Number <> 0 Then
        WScript.Echo "[SQL ERROR] Cannot connect to load functions: " & Err.Description
        WScript.Quit 1
    End If
    
    Set rs = CreateObject("ADODB.Recordset")
    rs.Open "SELECT Phase, ModuleName, FunctionName, Parameter FROM VbaFunctions ORDER BY Phase", conn
    
    If Err.Number <> 0 Then
        WScript.Echo "[SQL ERROR] Cannot query functions: " & Err.Description
        conn.Close
        WScript.Quit 1
    End If
    
    ' INITIALIZE ARRAYS
    Dim startList, innerList, endList, secondEndList
    startList = Array()
    innerList = Array()
    endList = Array()
    secondEndList = Array()
    
    Do Until rs.EOF
        phase = rs("Phase").Value
        moduleName = rs("ModuleName").Value
        functionName = rs("FunctionName").Value
        parameter = rs("Parameter").Value
        
        tempArray = Array(moduleName, functionName, parameter)
        
        If phase = "START" Then
            ReDim Preserve startList(UBound(startList) + 1)
            startList(UBound(startList)) = tempArray
        ElseIf phase = "INNER" Then
            ReDim Preserve innerList(UBound(innerList) + 1)
            innerList(UBound(innerList)) = tempArray
        ElseIf phase = "END" Then
            ReDim Preserve endList(UBound(endList) + 1)
            endList(UBound(endList)) = tempArray
        ElseIf phase = "SECOND_END" Then
            ReDim Preserve secondEndList(UBound(secondEndList) + 1)
            secondEndList(UBound(secondEndList)) = tempArray
        End If
        
        rs.MoveNext
    Loop
    
    rs.Close
    conn.Close
    
    ' ASSIGN GLOBAL ARRAYS
    If UBound(startList) >= 0 Then
        startFunctions = startList
    Else
        startFunctions = Array()
    End If
    If UBound(innerList) >= 0 Then
        innerFunctions = innerList
    Else
        innerFunctions = Array()
    End If
    If UBound(endList) >= 0 Then
        endFunctions = endList
    Else
        endFunctions = Array()
    End If
    If UBound(secondEndList) >= 0 Then
        secondEndFunctions = secondEndList
    Else
        secondEndFunctions = Array()
    End If
    
    WScript.Echo "[SQL] Loaded functions: START=" & UBound(startFunctions) + 1 & ", INNER=" & UBound(innerFunctions) + 1 & ", END=" & UBound(endFunctions) + 1 & ", SECOND_END=" & UBound(secondEndFunctions) + 1
End Sub

Function RunVbaFunctions(phase)
    On Error Resume Next
    Dim result, results, functions, i
    Err.Clear
    
    ' ENSURE EXCEL IS READY
    If wb Is Nothing Then
        WScript.Echo "    [" & phase & "] [ERROR] Workbook lost! Reopening..."
        Set xlApp = CreateObject("Excel.Application")
        xlApp.Visible = True
        Set wb = xlApp.Workbooks.Open(xlsmFile)
        wb.Activate
    End If
    
    ' SELECT FUNCTION ARRAY
    If phase = "START" Then
        functions = startFunctions
    ElseIf phase = "END" Then
        functions = endFunctions
    ElseIf phase = "SECOND_END" Then
        functions = secondEndFunctions
    Else ' INNER
        functions = innerFunctions
    End If
    
    ' HANDLE EMPTY FUNCTION LIST
    If UBound(functions) < 0 Then
        WScript.Echo "    [" & phase & "] No functions defined!"
        RunVbaFunctions = Array()
        Exit Function
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
    Dim conn, cmd, rs, i, jobStatus, ipAddress
    
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
    
    ' CONNECT TO SQL
    Set conn = CreateObject("ADODB.Connection")
    conn.ConnectionString = "Provider=SQLOLEDB;Server=YOUR_SERVER;Database=YOUR_DB;Trusted_Connection=Yes;"
    conn.Open
    
    If Err.Number <> 0 Then
        WScript.Echo "[SQL ERROR] Cannot connect: " & Err.Description
        LogResults Array(Array(Now(), -1, "SQL ERROR: " & Err.Description)), "SQL"
        Exit Sub
    End If
    
    ' CHECK CONTROL TABLE
    Set rs = CreateObject("ADODB.Recordset")
    rs.Open "SELECT TOP 1 ShouldStop FROM VbaControl ORDER BY CreatedAt DESC", conn
    
    If Not rs.EOF Then
        shouldStop = rs("ShouldStop").Value
        WScript.Echo "[CONTROL] ShouldStop = " & shouldStop
    Else
        WScript.Echo "[CONTROL] No control record found!"
    End If
    
    rs.Close
    
    ' CALL STORED PROCEDURE
    Set cmd = CreateObject("ADODB.Command")
    cmd.ActiveConnection = conn
    cmd.CommandType = 4
    cmd.CommandText = "UpdateVbaJobStatus"
    
    cmd.Parameters.Append cmd.CreateParameter("@IPAddress", 200, 1, 50, ipAddress)
    cmd.Parameters.Append cmd.CreateParameter("@JobStatus", 200, 1, 50, jobStatus)
    
    cmd.Execute
    
    If Err.Number <> 0 Then
        WScript.Echo "[SQL ERROR] Stored proc failed: " & Err.Description
        LogResults Array(Array(Now(), -1, "SQL ERROR: " & Err.Description)), "SQL"
    Else
        WScript.Echo "[SQL] Stored proc called: IP=" & ipAddress & ", Status=" & jobStatus
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