' import_module.vbs - ASCII ICONS ONLY
Option Explicit
Dim xlsmFile, basFile, moduleName
Dim xlApp, wb, vbProj, vbComp
Dim shell, fso, scriptDir

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' READ FROM CONSOLE VARIABLES
xlsmFile = shell.Environment("PROCESS")("EXCEL_FILE")
basFile = shell.Environment("PROCESS")("EXCEL_MODULE")

' VALIDATE INPUTS
If xlsmFile = "" Then
    MsgBox "ERROR: EXCEL_FILE not defined!" & vbCrLf & "Usage: set EXCEL_FILE=C:\Path\File.xlsm", vbCritical
    WScript.Quit 1
End If

If basFile = "" Then
    MsgBox "ERROR: EXCEL_MODULE not defined!" & vbCrLf & "Usage: set EXCEL_MODULE=C:\Path\Module1.bas", vbCritical
    WScript.Quit 1
End If

' STRIP QUOTES + CHECK FILES
If Left(xlsmFile, 1) = """" Then xlsmFile = Mid(xlsmFile, 2)
If Right(xlsmFile, 1) = """" Then xlsmFile = Left(xlsmFile, Len(xlsmFile) - 1)
If Left(basFile, 1) = """" Then basFile = Mid(basFile, 2)
If Right(basFile, 1) = """" Then basFile = Left(basFile, Len(basFile) - 1)

If Not fso.FileExists(xlsmFile) Then
    MsgBox "XLSM NOT FOUND: " & xlsmFile & vbCrLf & "Check path!", vbCritical
    WScript.Quit 1
End If

If Not fso.FileExists(basFile) Then
    MsgBox "BAS NOT FOUND: " & basFile & vbCrLf & "Check path!", vbCritical
    WScript.Quit 1
End If

moduleName = fso.GetBaseName(basFile)

WScript.Echo "[INFO] EXCEL_FILE:   " & xlsmFile
WScript.Echo "[INFO] EXCEL_MODULE: " & basFile
WScript.Echo "[INFO] Module Name:  " & moduleName
WScript.Echo ""

On Error Resume Next

' CREATE EXCEL
Set xlApp = CreateObject("Excel.Application")
If Err.Number <> 0 Then
    MsgBox "ERROR: Cannot create Excel! " & Err.Description, vbCritical
    WScript.Quit 1
End If
Err.Clear

xlApp.Visible = True
xlApp.DisplayAlerts = False

' OPEN XLSM
Set wb = xlApp.Workbooks.Open(xlsmFile)
If Err.Number <> 0 Then
    MsgBox "ERROR: Cannot open " & xlsmFile & vbCrLf & Err.Description, vbCritical
    xlApp.Quit
    WScript.Quit 1
End If
Err.Clear

WScript.Echo "[OK] Opened: " & wb.Name

' ACCESS VBA PROJECT
Set vbProj = wb.VBProject
If Err.Number <> 0 Then
    MsgBox "ERROR: Cannot access VBA Project!" & vbCrLf & "Enable: File > Options > Trust Center > Trust access to VBA", vbCritical
    wb.Close False
    xlApp.Quit
    WScript.Quit 1
End If
Err.Clear

' DELETE EXISTING MODULE
Set vbComp = vbProj.VBComponents(moduleName)
If Err.Number = 0 Then
    WScript.Echo "[OK] Deleting existing " & moduleName
    vbProj.VBComponents.Remove vbComp
End If
Err.Clear

' IMPORT BAS
WScript.Echo "[OK] Importing " & basFile & " into " & moduleName
vbProj.VBComponents.Import basFile
If Err.Number <> 0 Then
    MsgBox "ERROR: Cannot import " & basFile & vbCrLf & Err.Description, vbCritical
    wb.Close False
    xlApp.Quit
    WScript.Quit 1
End If
Err.Clear

WScript.Echo "[SUCCESS] " & moduleName & " imported!"
xlApp.DisplayAlerts = True
wb.Save

' SIMPLE LOCK - SINGLE OPEN FOREVER
xlApp.DisplayAlerts = True
wb.Save

xlApp.Visible = True
wb.Activate
xlApp.WindowState = -4137

' FIXED: SIMPLE LOCK FILE
Dim lockFile
lockFile = scriptDir & "\LOCKED_OPEN.txt"
fso.CreateTextFile(lockFile, True).Write "1"
WScript.Echo "[LOCK] Created: " & lockFile

' WScript.Sleep 2000
' MsgBox wb.Name & " LOCKED OPEN!" & vbCrLf & "Click OK for tests...", vbExclamation, "READY"

Set wb = Nothing
Set vbProj = Nothing
WScript.Quit 0