Option Explicit

' Global variables
Dim g_xlApp, g_wb
Dim g_conn, g_connInitialized
Dim g_fso, g_shell, g_scriptDir
Dim g_xlsmFile, g_TestId, g_UserRole, g_IpAddress
Dim g_logFile, g_FormattedNowStr
Dim g_server, g_database, g_username, g_password
Dim g_shouldStop
Dim g_DEV_MODE

' Configuration variables
Dim g_durationMin, g_numIterations
Dim g_secondDurationMin, g_secondNumIterations
Dim g_secondIterationCount, g_secondNextRun
Dim g_iterationCount
Dim g_startFunctions, g_innerFunctions, g_endFunctions
Dim g_secondEndFunctions, g_psoFunctions, g_pscFunctions

' Timing variables
Dim g_startTime, g_endTime

' Initialize the script
Call InitializeScript()

' Main execution
Call MainExecution()

' Cleanup
Call CleanupScript()

Sub InitializeScript()
    ' Set constants
    g_DEV_MODE = True
    
    ' Initialize objects
    Set g_shell = CreateObject("WScript.Shell")
    Set g_fso = CreateObject("Scripting.FileSystemObject")
    g_scriptDir = g_fso.GetParentFolderName(WScript.ScriptFullName)
    
    ' Get environment variables
    g_xlsmFile = g_shell.Environment("PROCESS")("eVTCS_Program")
    g_TestId = g_shell.Environment("PROCESS")("eVTCS_TestId")
    g_UserRole = g_shell.Environment("PROCESS")("eVTCS_User_Script")
    
    ' Get IP address
    g_IpAddress = GetIPAddress()
    If g_IpAddress = "" Then
        g_IpAddress = "UNKNOWN"
    End If
    
    ' Database configuration
    g_server = "10.100.104.189"
    g_database = "auto_test"
    g_username = "sa"
    g_password = "P@ssw0rd2025"
    
    ' Validate required variables
    If g_xlsmFile = "" Then
        WScript.Echo "[ERROR] EXCEL_FILE not defined!"
        WScript.Quit 1
    End If
    
    ' Strip quotes from xlsmFile
    If Left(g_xlsmFile, 1) = """" Then g_xlsmFile = Mid(g_xlsmFile, 2)
    If Right(g_xlsmFile, 1) = """" Then g_xlsmFile = Left(g_xlsmFile, Len(g_xlsmFile) - 1)
    
    ' Initialize flags
    g_shouldStop = False
    
    ' Setup log file
    g_FormattedNowStr = LogFileDT()
    g_logFile = "C:\Test\log\" & g_TestId & "-" & g_IpAddress & "-jmeter_logfile_" & g_FormattedNowStr & ".log"
    
    ' Create log file with header
    Dim logFileObj
    Set logFileObj = g_fso.CreateTextFile(g_logFile, True)
    logFileObj.WriteLine "Timestamp,Result,Parameter"
    logFileObj.Close
    Set logFileObj = Nothing
    
    WScript.Echo "[LOG] Writing to: " & g_logFile
End Sub

Sub MainExecution()
    ' Load configuration and functions
    WScript.Echo "[SQL] Loading configuration from database..."
    Call LoadConfig()
    
    WScript.Echo "[SQL] Loading VBA functions from database..."
    Call LoadVbaFunctions()
    
    ' Initialize Excel
    Call InitializeExcel()
    
    ' Start timing
    g_startTime = Now()
    g_endTime = DateAdd("n", g_durationMin * g_numIterations, g_startTime)
    
    WScript.Echo "[START TEST] " & FormatDateTime(g_startTime, 3)
    
    ' Pre-Test Setup Operations
    WScript.Echo "[PSO] " & FormatDateTime(g_startTime, 3)
    Dim psoResults
    psoResults = RunVbaFunctions("PSO")
    Call LogResults(psoResults, "PSO")
    
    WScript.Echo "[MAIN LOOP] " & g_numIterations & " iterations of " & g_durationMin & " min"
    WScript.Echo "[SECOND LOOP] " & g_secondNumIterations & " iterations of " & g_secondDurationMin & " min"
    WScript.Echo "[MAIN END] " & FormatDateTime(g_endTime, 3)
    WScript.Echo "[SECOND END] " & FormatDateTime(DateAdd("n", g_secondDurationMin * g_secondNumIterations, g_startTime), 3)
    WScript.Echo ""
    
    ' Initialize loop counters
    g_iterationCount = 0
    g_secondIterationCount = 0
    g_secondNextRun = DateAdd("n", g_secondDurationMin, g_startTime)
    
    Dim lastSqlUpdate
    lastSqlUpdate = Now()
    
    Call UpdateJobStatus("Running", "Test START")
    
    ' Main execution loop
    Call ExecuteMainLoop(lastSqlUpdate)
    
    ' Post-Test Cleanup Operations
    WScript.Echo "[PSC] " & FormatDateTime(Now(), 3)
    Dim pscResults
    pscResults = RunVbaFunctions("PSC")
    Call LogResults(pscResults, "PSC")
    
    Call UpdateJobStatus("Completed", "Test Completed")
    WScript.Echo "[COMPLETED] " & FormatDateTime(Now(), 3)
End Sub

Sub ExecuteMainLoop(ByRef lastSqlUpdate)
    Do While g_iterationCount < g_numIterations
        g_iterationCount = g_iterationCount + 1
        WScript.Echo FormatDateTime(Now, 3) & " [VT PERIOD] " & g_iterationCount & " START"
        Call UpdateJobStatus("Running", "[VT PERIOD] " & g_iterationCount & " START")
        
        ' Run START functions
        Dim startResults
        startResults = RunVbaFunctions("START")
        Call LogResults(startResults, "START")
        
        ' Inner loop (high-frequency execution)
        Call ExecuteInnerLoop(lastSqlUpdate)
        
        ' Run END functions
        Dim endResults
        endResults = RunVbaFunctions("END")
        Call LogResults(endResults, "END")
        
        WScript.Echo FormatDateTime(Now, 3) & " [VT PERIOD] " & g_iterationCount & " END"
        
        If Now() >= g_endTime Or g_shouldStop Then
            WScript.Echo FormatDateTime(Now, 3) & " [DONE] Total main end time reached!"
            Exit Do
        End If
    Loop
End Sub

Sub ExecuteInnerLoop(ByRef lastSqlUpdate)
    Dim iterationEndTime
    iterationEndTime = DateAdd("n", g_durationMin, Now())
    
    Do While Now() < iterationEndTime
        If Now() >= g_endTime Or g_shouldStop Then
            WScript.Echo FormatDateTime(Now, 3) & " [DONE] Main end time reached or stop signaled!"
            Exit Do
        End If
        
        ' Run INNER functions
        Dim innerResults
        innerResults = RunVbaFunctions("INNER")
        Call LogResults(innerResults, "INNER")
        
        ' Check for second loop execution
        Call CheckSecondLoop(lastSqlUpdate)
        
        ' SQL update every minute
        If DateDiff("s", lastSqlUpdate, Now()) >= 60 Then
            Call UpdateJobStatus("Running", "Heart beat")
            lastSqlUpdate = Now()
        End If
        
        WScript.Sleep 3000
    Loop
End Sub

Sub CheckSecondLoop(ByRef lastSqlUpdate)
    If g_secondIterationCount < g_secondNumIterations And Now() >= g_secondNextRun Then
        g_secondIterationCount = g_secondIterationCount + 1
        WScript.Echo FormatDateTime(Now, 3) & " [CS PERIOD] " & g_secondIterationCount & " CUT-OFF"
        
        ' Run SECOND_END functions
        Dim secondEndResults
        secondEndResults = RunVbaFunctions("SECOND_END")
        Call LogResults(secondEndResults, "SECOND_END")
        
        WScript.Echo FormatDateTime(Now, 3) & " [CS PERIOD] " & g_secondIterationCount & " END"
        g_secondNextRun = DateAdd("n", g_secondDurationMin, g_secondNextRun)
    End If
End Sub

Sub InitializeExcel()
    On Error Resume Next
    Set g_xlApp = Nothing
    WScript.Echo "[OPEN] Connecting to Excel..."
    
    Set g_xlApp = GetObject(, "Excel.Application")
    If Err.Number <> 0 Then
        WScript.Echo "    [OPEN] No Excel running! Opening: " & g_xlsmFile
        Set g_xlApp = CreateObject("Excel.Application")
        g_xlApp.Visible = True
        Set g_wb = g_xlApp.Workbooks.Open(g_xlsmFile)
        g_wb.Activate
    Else
        Set g_wb = g_xlApp.ActiveWorkbook
        g_wb.Activate
        WScript.Echo "    [REUSED] " & g_wb.Name
    End If
    Err.Clear
    On Error GoTo 0
    
    If g_wb Is Nothing Then
        WScript.Echo "[FATAL] Cannot open workbook!"
        WScript.Quit 1
    End If
End Sub

Sub LoadConfig()
    On Error Resume Next
    
    Dim conn, cmd, query, rs
    Set conn = CreateObject("ADODB.Connection")
    
    ' Use connection function
    Call OpenConnection(conn)
    
    ' Build query with parameterized approach (basic protection)
    query = "SELECT TOP 1 VTDurationMin, NumOfVTPeriod, CSDurationMin, NumOfCSPeriod FROM TestControl WHERE TestId = ?"
    
    Set cmd = CreateObject("ADODB.Command")
    cmd.ActiveConnection = conn
    cmd.CommandText = Replace(query, "?", "'" & EscapeSql(g_TestId) & "'")
    cmd.CommandType = 1  ' adCmdText
    
    Set rs = cmd.Execute
    
    If Err.Number <> 0 Then
        WScript.Echo "[SQL ERROR] Cannot query config: " & Err.Description
        WScript.Quit 1
    End If
    
    ' Set default values
    g_durationMin = 1
    g_numIterations = 4
    g_secondDurationMin = 1
    g_secondNumIterations = 2
    
    If Not rs.EOF Then
        g_durationMin = CInt(rs.Fields("VTDurationMin").Value)
        g_numIterations = CInt(rs.Fields("NumOfVTPeriod").Value)
        g_secondDurationMin = CInt(rs.Fields("CSDurationMin").Value)
        g_secondNumIterations = CInt(rs.Fields("NumOfCSPeriod").Value)
    End If
    
    rs.Close
    conn.Close
    
    Set rs = Nothing
    Set cmd = Nothing
    Set conn = Nothing
    
    WScript.Echo "[SQL] Loaded config: MainDurationMin=" & g_durationMin & ", MainIterations=" & g_numIterations & ", SecondDurationMin=" & g_secondDurationMin & ", SecondIterations=" & g_secondNumIterations
End Sub

Sub LoadVbaFunctions()
    On Error Resume Next
    
    Dim conn, rs, phase, moduleName, functionName, parameter, tempArray
    Set conn = CreateObject("ADODB.Connection")
    
    Call OpenConnection(conn)
    
    ' Build query with parameterized approach
    Dim query
    query = "SELECT Phase, ModuleName, FunctionName, Parameter FROM TestCase WHERE UserRole = '" & EscapeSql(g_UserRole) & "' OR UserRole = SUBSTRING('" & EscapeSql(g_UserRole) & "', 1, 1) ORDER BY Phase, Sequence"
    
    Set rs = CreateObject("ADODB.Recordset")
    rs.Open query, conn
    
    If Err.Number <> 0 Then
        WScript.Echo "[SQL ERROR] Cannot query functions: " & Err.Description
        WScript.Quit 1
    End If
    
    ' Initialize arrays
    Dim startList, innerList, endList, secondEndList, psoList, pscList
    startList = Array()
    innerList = Array()
    endList = Array()
    secondEndList = Array()
    psoList = Array()
    pscList = Array()
    
    Do Until rs.EOF
        phase = rs("Phase").Value
        moduleName = rs("ModuleName").Value
        functionName = rs("FunctionName").Value
        parameter = rs("Parameter").Value
        
        tempArray = Array(moduleName, functionName, parameter)
        
        Select Case phase
            Case "PSO"
                startList = AddToArray(psoList, tempArray)
            Case "PSC"
                startList = AddToArray(pscList, tempArray)
            Case "START"
                startList = AddToArray(startList, tempArray)
            Case "INNER"
                startList = AddToArray(innerList, tempArray)
            Case "END"
                startList = AddToArray(endList, tempArray)
            Case "SECOND_END"
                startList = AddToArray(secondEndList, tempArray)
        End Select
        
        rs.MoveNext
    Loop
    
    rs.Close
    conn.Close
    
    Set rs = Nothing
    Set conn = Nothing
    
    ' Assign to global variables
    g_psoFunctions = psoList
    g_pscFunctions = pscList
    g_startFunctions = startList
    g_innerFunctions = innerList
    g_endFunctions = endList
    g_secondEndFunctions = secondEndList
    
    WScript.Echo "[SQL] Loaded functions: START=" & (UBound(g_startFunctions) + 1) & ", INNER=" & (UBound(g_innerFunctions) + 1) & ", END=" & (UBound(g_endFunctions) + 1) & _
                  ", SECOND_END=" & (UBound(g_secondEndFunctions) + 1) & ", PSO=" & (UBound(g_psoFunctions) + 1) & ", PSC=" & (UBound(g_pscFunctions) + 1)
End Sub

Function RunVbaFunctions(phase)
    On Error Resume Next
    Err.Clear
    
    ' Ensure Excel is ready
    If g_wb Is Nothing Then
        WScript.Echo "    [" & phase & "] [ERROR] Workbook lost! Reopening..."
        Call InitializeExcel()
    End If
    
    ' Select function array based on phase
    Dim functions
    Select Case phase
        Case "PSO"
            functions = g_psoFunctions
        Case "PSC"
            functions = g_pscFunctions
        Case "START"
            functions = g_startFunctions
        Case "END"
            functions = g_endFunctions
        Case "SECOND_END"
            functions = g_secondEndFunctions
        Case Else ' INNER
            functions = g_innerFunctions
    End Select
    
    If IsEmpty(functions) Or UBound(functions) = -1 Then
        ReDim functions(-1) ' Empty array
    End If
    
    Dim results()
    ReDim results(UBound(functions))
    
    Dim i, result, functionInfo
    For i = 0 To UBound(functions)
        If UBound(functions) >= 0 Then
            functionInfo = functions(i)
            WScript.Echo "    " & FormatDateTime(Now, 3) & " [" & phase & "] " & functionInfo(0) & "." & functionInfo(1) & "( """ & functionInfo(2) & """ )"
            
            result = g_wb.Application.Run(functionInfo(0) & "." & functionInfo(1), """" & functionInfo(2) & """")
            
            If Err.Number = 0 Then
                results(i) = Array(Now(), CDbl(result), functionInfo(2))
                WScript.Echo "    [SUCCESS] " & CInt(result)
            Else
                results(i) = Array(Now(), -1, functionInfo(2) & " ERROR: " & Err.Number)
                WScript.Echo "    [ERROR] " & Err.Number & ": " & CleanError(Err.Description)
                Err.Clear
            End If
        End If
    Next
    
    RunVbaFunctions = results
End Function

Sub LogResults(results, phase)
    On Error Resume Next
    
    Dim file, i
    Set file = g_fso.OpenTextFile(g_logFile, 8, True) ' 8 = ForAppending
    
    For i = 0 To UBound(results)
        If IsArray(results(i)) And UBound(results(i)) >= 2 Then
            file.WriteLine LogDataDT(results(i)(0)) & "," & CInt(results(i)(1)) & "," & results(i)(2)
        End If
    Next
    
    file.Close
    Set file = Nothing
End Sub

Sub UpdateJobStatus(jobStatus, jobDetails)
    On Error Resume Next
    
    Dim conn, cmd, rs
    Set conn = CreateObject("ADODB.Connection")
    
    Call OpenConnection(conn)
    
    If Err.Number <> 0 Then
        WScript.Echo "Connection error: " & Err.Description
        Call LogResults(Array(Array(Now(), -1, "SQL ERROR: " & Err.Description)), "SQL")
        Exit Sub
    End If
    
    ' Check control table
    Set rs = CreateObject("ADODB.Recordset")
    Dim controlQuery
    controlQuery = "SELECT TOP 1 TestId FROM Testcontrol WHERE testid = '" & EscapeSql(g_TestId) & "' AND (GETDATE() > EndTime OR Status IN ('Aborted', 'Completed'))"
    rs.Open controlQuery, conn
    
    If Not rs.EOF Then
        g_shouldStop = True
        WScript.Echo "[CONTROL] Test End Signaled."
    End If
    
    rs.Close
    Set rs = Nothing
    
    ' Call stored procedure
    Set cmd = CreateObject("ADODB.Command")
    cmd.ActiveConnection = conn
    cmd.CommandType = 4 ' adCmdStoredProc
    cmd.CommandText = "UpdateJobStatusWithHistory"
    
    cmd.Parameters.Append cmd.CreateParameter("@ClientIp", 200, 1, 50, g_IpAddress) ' adVarChar
    cmd.Parameters.Append cmd.CreateParameter("@Status", 200, 1, 50, jobStatus)
    cmd.Parameters.Append cmd.CreateParameter("@Details", 200, 1, 500, jobDetails)
    
    cmd.Execute
    
    If Err.Number <> 0 Then
        WScript.Echo "[SQL ERROR] Stored proc failed: " & Err.Description
        Call LogResults(Array(Array(Now(), -1, "SQL ERROR: " & Err.Description)), "SQL")
    Else
        WScript.Echo "[SQL] Stored proc called: IP=" & g_IpAddress & ", Status=" & jobStatus
    End If
    
    conn.Close
    Set cmd = Nothing
    Set conn = Nothing
End Sub

Sub OpenConnection(ByRef conn)
    On Error Resume Next
    
    Dim connString
    connString = "Provider=SQLOLEDB;Data Source=" & g_server & ";Initial Catalog=" & g_database & _
                 ";User ID=" & g_username & ";Password=" & g_password & ";Connection Timeout=30;"
    
    conn.Open connString
    
    If Err.Number <> 0 Then
        WScript.Echo "[ERROR] Cannot connect to database: " & Err.Description
        WScript.Quit 1
    End If
    
    Err.Clear
    On Error GoTo 0
End Sub

Function AddToArray(arr, newItem)
    Dim newSize
    If IsEmpty(arr) Then
        ReDim arr(0)
        arr(0) = newItem
    Else
        newSize = UBound(arr) + 1
        ReDim Preserve arr(newSize)
        arr(newSize) = newItem
    End If
    AddToArray = arr
End Function

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

Function EscapeSql(sqlText)
    ' Basic SQL injection protection
    EscapeSql = Replace(Replace(sqlText, "'", "''"), ";", "")
End Function

Function LogFileDT()
    Dim dt
    dt = Now
    
    Dim yearPart, monthPart, dayPart, hourPart
    yearPart = Year(dt)
    monthPart = Right("0" & Month(dt), 2)
    dayPart = Right("0" & Day(dt), 2)
    hourPart = Right("0" & Hour(dt), 2)
    
    LogFileDT = yearPart & monthPart & dayPart & "-" & hourPart
End Function

Function LogDataDT(timestamp)
    If Not IsDate(timestamp) Then
        LogDataDT = "Invalid Date"
        Exit Function
    End If
    
    Dim dt : dt = CDate(timestamp)
    
    Dim dateStr : dateStr = Year(dt) & "/" & Right("0" & Month(dt), 2) & "/" & Right("0" & Day(dt), 2)
    Dim timeStr : timeStr = Right("0" & Hour(dt), 2) & ":" & Right("0" & Minute(dt), 2) & ":" & Right("0" & Second(dt), 2)
    Dim ms : ms = Right("000" & CStr(Int((Timer - Int(Timer)) * 1000)), 3)
    
    LogDataDT = dateStr & " " & timeStr & "." & ms
End Function

Sub CleanupScript()
    On Error Resume Next
    
    ' Close Excel
    If Not g_wb Is Nothing Then
        g_wb.Close False
        Set g_wb = Nothing
    End If
    
    If Not g_xlApp Is Nothing Then
        g_xlApp.Quit
        Set g_xlApp = Nothing
    End If
    
    ' Close database connection
    If Not g_conn Is Nothing Then
        g_conn.Close
        Set g_conn = Nothing
    End If
    
    ' Clean up other objects
    Set g_fso = Nothing
    Set g_shell = Nothing
    
    WScript.Echo "[CLEANUP] Script completed successfully"
End Sub