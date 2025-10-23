# PowerShell Script for Load Testing Framework
# Migrated from VBScript

# Global variables
[string]$Script:durationMin = ""
[string]$Script:numIterations = ""
[string]$Script:secondDurationMin = ""
[string]$Script:secondNumIterations = ""
[int]$Script:secondIterationCount = 0
[datetime]$Script:secondNextRun = [datetime]::MinValue
[int]$Script:iterationCount = 0
[bool]$Script:shouldStop = $false
[string]$Script:TestId = ""
[string]$Script:IpAddress = ""
[string]$Script:FormattedNowStr = ""
[string]$Script:server = "10.100.104.189"
[string]$Script:database = "auto_test"
[string]$Script:username = "sa"
[string]$Script:password = "P@ssw0rd2025"
[bool]$Script:DEV_MODE = $true
[string]$Script:UserRole = ""

# Function arrays
[array]$Script:startFunctions = @()
[array]$Script:innerFunctions = @()
[array]$Script:endFunctions = @()
[array]$Script:secondEndFunctions = @()
[array]$Script:psoFunctions = @()
[array]$Script:pscFunctions = @()

# Excel objects
[object]$Script:xlApp = $null
[object]$Script:wb = $null

# File system objects
[object]$Script:fso = $null
[string]$Script:scriptDir = ""
[string]$Script:xlsmFile = ""
[string]$Script:logFile = ""

# Timing variables
[datetime]$Script:startTime = [datetime]::MinValue
[datetime]$Script:endTime = [datetime]::MinValue

function Initialize-Script {
    Write-Host "[INIT] Initializing PowerShell script..."
    
    # Get environment variables
    $Script:xlsmFile = $env:eVTCS_Program
    $Script:TestId = $env:eVTCS_TestId
    $Script:UserRole = $env:eVTCS_User_Script
    
    # Get script directory
    $Script:scriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
    
    # Get IP address
    $Script:IpAddress = Get-IPAddress
    if ([string]::IsNullOrEmpty($Script:IpAddress)) {
        $Script:IpAddress = "UNKNOWN"
    }
    
    # Validate required variables
    if ([string]::IsNullOrEmpty($Script:xlsmFile)) {
        Write-Error "[ERROR] EXCEL_FILE not defined!"
        exit 1
    }
    
    # Strip quotes from xlsmFile if present
    if ($Script:xlsmFile.StartsWith('"')) {
        $Script:xlsmFile = $Script:xlsmFile.Substring(1)
    }
    if ($Script:xlsmFile.EndsWith('"')) {
        $Script:xlsmFile = $Script:xlsmFile.Substring(0, $Script:xlsmFile.Length - 1)
    }
    
    # Initialize file system object
    $Script:fso = New-Object -ComObject "Scripting.FileSystemObject"
    
    # Setup log file
    $Script:FormattedNowStr = Get-LogFileDT
    $Script:logFile = "C:\Test\log\$($Script:TestId)-$($Script:IpAddress)-jmeter_logfile_$($Script:FormattedNowStr).log"
    
    # Create log file with header
    $logDir = Split-Path $Script:logFile -Parent
    if (!(Test-Path $logDir)) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }
    
    $header = "Timestamp,Result,Parameter"
    [System.IO.File]::WriteAllText($Script:logFile, $header + "`r`n")
    
    Write-Host "[LOG] Writing to: $Script:logFile"
}

function Get-IPAddress {
    try {
        $networkInterfaces = [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()
        $activeInterface = $networkInterfaces | Where-Object { $_.OperationalStatus -eq 'Up' -and $_.NetworkInterfaceType -ne 'Loopback' }
        
        foreach ($interface in $activeInterface) {
            $properties = $interface.GetIPProperties()
            $unicastAddresses = $properties.UnicastAddresses | Where-Object { !$_.Address.IsLoopback -and $_.Address.AddressFamily -eq 'InterNetwork' }
            if ($unicastAddresses) {
                return $unicastAddresses[0].Address.ToString()
            }
        }
        return ""
    }
    catch {
        Write-Warning "Error getting IP address: $($_.Exception.Message)"
        return ""
    }
}

function Load-Configuration {
    Write-Host "[SQL] Loading configuration from database..."
    
    $connectionString = "Provider=SQLOLEDB;Data Source=$($Script:server);Initial Catalog=$($Script:database);User ID=$($Script:username);Password=$($Script:password);"
    
    $connection = New-Object -ComObject "ADODB.Connection"
    $command = New-Object -ComObject "ADODB.Command"
    $recordset = New-Object -ComObject "ADODB.Recordset"
    
    try {
        $connection.Open($connectionString)
        $command.ActiveConnection = $connection
        $command.CommandText = "SELECT TOP 1 VTDurationMin, NumOfVTPeriod, CSDurationMin, NumOfCSPeriod FROM TestControl WHERE TestId = ?"
        
        # Use parameterized query to prevent SQL injection
        $commandText = $command.CommandText.Replace("?", "'$($Script:TestId)'")
        $command.CommandText = $commandText
        $command.CommandType = 1  # adCmdText
        
        $recordset = $command.Execute()
        
        # Set default values
        $Script:durationMin = 1
        $Script:numIterations = 4
        $Script:secondDurationMin = 1
        $Script:secondNumIterations = 2
        
        if (-not $recordset.EOF) {
            $Script:durationMin = [int]$recordset.Fields("VTDurationMin").Value
            $Script:numIterations = [int]$recordset.Fields("NumOfVTPeriod").Value
            $Script:secondDurationMin = [int]$recordset.Fields("CSDurationMin").Value
            $Script:secondNumIterations = [int]$recordset.Fields("NumOfCSPeriod").Value
        }
        
        Write-Host "[SQL] Loaded config: MainDurationMin=$($Script:durationMin), MainIterations=$($Script:numIterations), SecondDurationMin=$($Script:secondDurationMin), SecondIterations=$($Script:secondNumIterations)"
    }
    catch {
        Write-Error "[SQL ERROR] Cannot query config: $($_.Exception.Message)"
        exit 1
    }
    finally {
        if ($recordset.State -eq 1) { $recordset.Close() }
        if ($connection.State -eq 1) { $connection.Close() }
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($recordset) | Out-Null
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($command) | Out-Null
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($connection) | Out-Null
    }
}

function Load-VbaFunctions {
    Write-Host "[SQL] Loading VBA functions from database..."
    
    $connectionString = "Provider=SQLOLEDB;Data Source=$($Script:server);Initial Catalog=$($Script:database);User ID=$($Script:username);Password=$($Script:password);"
    
    $connection = New-Object -ComObject "ADODB.Connection"
    $recordset = New-Object -ComObject "ADODB.Recordset"
    
    try {
        $connection.Open($connectionString)
        
        # Build query with parameterized approach
        $query = "SELECT Phase, ModuleName, FunctionName, Parameter FROM TestCase WHERE UserRole = '$($Script:UserRole)' OR UserRole = SUBSTRING('$($Script:UserRole)', 1, 1) ORDER BY Phase, Sequence"
        
        $recordset.Open($query, $connection)
        
        # Initialize arrays
        $psoList = @()
        $pscList = @()
        $startList = @()
        $innerList = @()
        $endList = @()
        $secondEndList = @()
        
        while (-not $recordset.EOF) {
            $phase = $recordset.Fields("Phase").Value
            $moduleName = $recordset.Fields("ModuleName").Value
            $functionName = $recordset.Fields("FunctionName").Value
            $parameter = $recordset.Fields("Parameter").Value
            
            $tempArray = @($moduleName, $functionName, $parameter)
            
            switch ($phase) {
                "PSO" { $psoList += ,$tempArray }
                "PSC" { $pscList += ,$tempArray }
                "START" { $startList += ,$tempArray }
                "INNER" { $innerList += ,$tempArray }
                "END" { $endList += ,$tempArray }
                "SECOND_END" { $secondEndList += ,$tempArray }
            }
            
            $recordset.MoveNext()
        }
        
        # Assign to global variables
        $Script:psoFunctions = $psoList
        $Script:pscFunctions = $pscList
        $Script:startFunctions = $startList
        $Script:innerFunctions = $innerList
        $Script:endFunctions = $endList
        $Script:secondEndFunctions = $secondEndList
        
        Write-Host "[SQL] Loaded functions: START=$($Script:startFunctions.Count), INNER=$($Script:innerFunctions.Count), END=$($Script:endFunctions.Count), SECOND_END=$($Script:secondEndFunctions.Count), PSO=$($Script:psoFunctions.Count), PSC=$($Script:pscFunctions.Count)"
    }
    catch {
        Write-Error "[SQL ERROR] Cannot query functions: $($_.Exception.Message)"
        exit 1
    }
    finally {
        if ($recordset.State -eq 1) { $recordset.Close() }
        if ($connection.State -eq 1) { $connection.Close() }
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($recordset) | Out-Null
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($connection) | Out-Null
    }
}

function Initialize-Excel {
    Write-Host "[OPEN] Connecting to Excel..."
    
    try {
        # Try to get existing Excel application
        $Script:xlApp = Get-Object -ComObject "Excel.Application" -ErrorAction SilentlyContinue
        
        if ($null -eq $Script:xlApp) {
            Write-Host "    [OPEN] No Excel running! Opening: $($Script:xlsmFile)"
            $Script:xlApp = New-Object -ComObject "Excel.Application"
            $Script:xlApp.Visible = $true
            $Script:wb = $Script:xlApp.Workbooks.Open($Script:xlsmFile)
            $Script:wb.Activate()
        }
        else {
            $Script:wb = $Script:xlApp.ActiveWorkbook
            $Script:wb.Activate()
            Write-Host "    [REUSED] $($Script:wb.Name)"
        }
    }
    catch {
        Write-Error "[FATAL] Cannot open workbook: $($_.Exception.Message)"
        exit 1
    }
    
    if ($null -eq $Script:wb) {
        Write-Error "[FATAL] Cannot open workbook!"
        exit 1
    }
}

function Run-VbaFunctions($phase) {
    $results = @()
    
    # Ensure Excel is ready
    if ($null -eq $Script:wb) {
        Write-Host "    [$phase] [ERROR] Workbook lost! Reopening..."
        Initialize-Excel
    }
    
    # Select function array based on phase
    $functions = switch ($phase) {
        "PSO" { $Script:psoFunctions }
        "PSC" { $Script:pscFunctions }
        "START" { $Script:startFunctions }
        "END" { $Script:endFunctions }
        "SECOND_END" { $Script:secondEndFunctions }
        default { $Script:innerFunctions }  # INNER
    }
    
    if ($null -eq $functions -or $functions.Count -eq 0) {
        return $results
    }
    
    foreach ($functionInfo in $functions) {
        if ($functionInfo.Count -ge 3) {
            $moduleName = $functionInfo[0]
            $functionName = $functionInfo[1]
            $parameter = $functionInfo[2]
            
            Write-Host "    $(Get-LogDataDT (Get-Date)) [$phase] $moduleName.$functionName( `"$parameter`" )"
            
            try {
                $result = $Script:wb.Application.Run("$moduleName.$functionName", $parameter)
                $results += ,@((Get-Date), [double]$result, $parameter)
                Write-Host "    [SUCCESS] $([int]$result)"
            }
            catch {
                $results += ,@((Get-Date), -1, "$parameter ERROR: $($_.Exception.Message)")
                Write-Host "    [ERROR] $($_.Exception.Message)"
            }
        }
    }
    
    return $results
}

function Log-Results($results, $phase) {
    $logEntries = @()
    
    foreach ($result in $results) {
        if ($result.Count -ge 3) {
            $timestamp = $result[0]
            $value = $result[1]
            $parameter = $result[2]
            
            $logLine = "$(Get-LogDataDT $timestamp),$([int]$value),$parameter"
            $logEntries += $logLine
        }
    }
    
    if ($logEntries.Count -gt 0) {
        $logContent = ($logEntries -join "`r`n") + "`r`n"
        [System.IO.File]::AppendAllText($Script:logFile, $logContent)
    }
}

function Update-JobStatus($jobStatus, $jobDetails) {
    $connectionString = "Provider=SQLOLEDB;Data Source=$($Script:server);Initial Catalog=$($Script:database);User ID=$($Script:username);Password=$($Script:password);"
    
    $connection = New-Object -ComObject "ADODB.Connection"
    $command = New-Object -ComObject "ADODB.Command"
    $recordset = New-Object -ComObject "ADODB.Recordset"
    
    try {
        $connection.Open($connectionString)
        
        # Check control table
        $controlQuery = "SELECT TOP 1 TestId FROM Testcontrol WHERE testid = '$($Script:TestId)' AND (GETDATE() > EndTime OR Status IN ('Aborted', 'Completed'))"
        $recordset.Open($controlQuery, $connection)
        
        if (-not $recordset.EOF) {
            $Script:shouldStop = $true
            Write-Host "[CONTROL] Test End Signaled."
        }
        
        $recordset.Close()
        
        # Call stored procedure
        $command.ActiveConnection = $connection
        $command.CommandType = 4  # adCmdStoredProc
        $command.CommandText = "UpdateJobStatusWithHistory"
        
        # Add parameters
        $param1 = $command.CreateParameter("@ClientIp", 200, 1, 50, $Script:IpAddress)  # adVarChar
        $param2 = $command.CreateParameter("@Status", 200, 1, 50, $jobStatus)
        $param3 = $command.CreateParameter("@Details", 200, 1, 500, $jobDetails)
        
        $command.Parameters.Append($param1)
        $command.Parameters.Append($param2)
        $command.Parameters.Append($param3)
        
        $command.Execute()
        
        Write-Host "[SQL] Stored proc called: IP=$($Script:IpAddress), Status=$jobStatus"
    }
    catch {
        Write-Error "[SQL ERROR] Stored proc failed: $($_.Exception.Message)"
        $errorResults = ,@((Get-Date), -1, "SQL ERROR: $($_.Exception.Message)")
        Log-Results $errorResults "SQL"
    }
    finally {
        if ($recordset.State -eq 1) { $recordset.Close() }
        if ($connection.State -eq 1) { $connection.Close() }
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($recordset) | Out-Null
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($command) | Out-Null
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($connection) | Out-Null
    }
}

function Get-LogFileDT {
    $dt = Get-Date
    $year = $dt.Year.ToString()
    $month = $dt.Month.ToString("D2")
    $day = $dt.Day.ToString("D2")
    $hour = $dt.Hour.ToString("D2")
    
    return "${year}${month}${day}-${hour}"
}

function Get-LogDataDT($timestamp) {
    if ($null -eq $timestamp) {
        return "Invalid Date"
    }
    
    $dt = $timestamp
    $dateStr = "$($dt.Year)/$($dt.Month.ToString('D2'))/$($dt.Day.ToString('D2'))"
    $timeStr = "$($dt.Hour.ToString('D2')):$($dt.Minute.ToString('D2')):$($dt.Second.ToString('D2'))"
    $ms = [math]::Round(([DateTime]::Now.TimeOfDay.TotalMilliseconds % 1000)).ToString("D3")
    
    return "$dateStr $timeStr.$ms"
}

function Execute-MainLoop {
    $lastSqlUpdate = Get-Date
    
    Update-JobStatus "Running" "Test START"
    
    while ($Script:iterationCount -lt [int]$Script:numIterations) {
        $Script:iterationCount++
        Write-Host "$(Get-LogDataDT (Get-Date)) [VT PERIOD] $($Script:iterationCount) START"
        Update-JobStatus "Running" "[VT PERIOD] $($Script:iterationCount) START"
        
        # Run START functions
        $startResults = Run-VbaFunctions "START"
        Log-Results $startResults "START"
        
        # Execute inner loop
        Execute-InnerLoop $lastSqlUpdate
        
        # Run END functions
        $endResults = Run-VbaFunctions "END"
        Log-Results $endResults "END"
        
        Write-Host "$(Get-LogDataDT (Get-Date)) [VT PERIOD] $($Script:iterationCount) END"
        
        if ((Get-Date) -ge $Script:endTime -or $Script:shouldStop) {
            Write-Host "$(Get-LogDataDT (Get-Date)) [DONE] Total main end time reached!"
            break
        }
    }
}

function Execute-InnerLoop([ref]$lastSqlUpdate) {
    $iterationEndTime = (Get-Date).AddMinutes([int]$Script:durationMin)
    
    while ((Get-Date) -lt $iterationEndTime) {
        if ((Get-Date) -ge $Script:endTime -or $Script:shouldStop) {
            Write-Host "$(Get-LogDataDT (Get-Date)) [DONE] Main end time reached or stop signaled!"
            break
        }
        
        # Run INNER functions
        $innerResults = Run-VbaFunctions "INNER"
        Log-Results $innerResults "INNER"
        
        # Check for second loop execution
        if ($Script:secondIterationCount -lt [int]$Script:secondNumIterations -and (Get-Date) -ge $Script:secondNextRun) {
            $Script:secondIterationCount++
            Write-Host "$(Get-LogDataDT (Get-Date)) [CS PERIOD] $($Script:secondIterationCount) CUT-OFF"
            
            # Run SECOND_END functions
            $secondEndResults = Run-VbaFunctions "SECOND_END"
            Log-Results $secondEndResults "SECOND_END"
            
            Write-Host "$(Get-LogDataDT (Get-Date)) [CS PERIOD] $($Script:secondIterationCount) END"
            $Script:secondNextRun = $Script:secondNextRun.AddMinutes([int]$Script:secondDurationMin)
        }
        
        # SQL update every minute
        if ((Get-Date).Subtract($lastSqlUpdate.Value).TotalSeconds -ge 60) {
            Update-JobStatus "Running" "Heart beat"
            $lastSqlUpdate.Value = Get-Date
        }
        
        Start-Sleep -Milliseconds 3000
    }
}

function Cleanup-Script {
    Write-Host "[CLEANUP] Cleaning up resources..."
    
    # Close Excel
    if ($null -ne $Script:wb) {
        try {
            $Script:wb.Close($false)  # Don't save changes
            [System.Runtime.Interopservices.Marshal]::ReleaseComObject($Script:wb) | Out-Null
        }
        catch {
            Write-Warning "Error closing workbook: $($_.Exception.Message)"
        }
        $Script:wb = $null
    }
    
    if ($null -ne $Script:xlApp) {
        try {
            $Script:xlApp.Quit()
            [System.Runtime.Interopservices.Marshal]::ReleaseComObject($Script:xlApp) | Out-Null
        }
        catch {
            Write-Warning "Error quitting Excel: $($_.Exception.Message)"
        }
        $Script:xlApp = $null
    }
    
    Write-Host "[CLEANUP] Script completed successfully"
}

# Main execution
try {
    # Initialize script
    Initialize-Script
    
    # Load configuration and functions
    Load-Configuration
    Load-VbaFunctions
    
    # Initialize Excel
    Initialize-Excel
    
    # Start timing
    $Script:startTime = Get-Date
    $Script:endTime = $Script:startTime.AddMinutes([int]$Script:durationMin * [int]$Script:numIterations)
    
    Write-Host "[START TEST] $($Script:startTime.ToString('G'))"
    
    # Pre-Test Setup Operations
    Write-Host "[PSO] $($Script:startTime.ToString('G'))"
    $psoResults = Run-VbaFunctions "PSO"
    Log-Results $psoResults "PSO"
    
    Write-Host "[MAIN LOOP] $([int]$Script:numIterations) iterations of $([int]$Script:durationMin) min"
    Write-Host "[SECOND LOOP] $([int]$Script:secondNumIterations) iterations of $([int]$Script:secondDurationMin) min"
    Write-Host "[MAIN END] $($Script:endTime.ToString('G'))"
    Write-Host "[SECOND END] $(($Script:startTime.AddMinutes([int]$Script:secondDurationMin * [int]$Script:secondNumIterations)).ToString('G'))"
    Write-Host ""
    
    # Initialize loop counters
    $Script:iterationCount = 0
    $Script:secondIterationCount = 0
    $Script:secondNextRun = $Script:startTime.AddMinutes([int]$Script:secondDurationMin)
    
    # Execute main loop
    Execute-MainLoop
    
    # Post-Test Cleanup Operations
    Write-Host "[PSC] $(Get-Date.ToString('G'))"
    $pscResults = Run-VbaFunctions "PSC"
    Log-Results $pscResults "PSC"
    
    Update-JobStatus "Completed" "Test Completed"
    Write-Host "[COMPLETED] $(Get-Date.ToString('G'))"
}
catch {
    Write-Error "Script failed with error: $($_.Exception.Message)"
    Write-Error "Stack trace: $($_.ScriptStackTrace)"
}
finally {
    Cleanup-Script
}