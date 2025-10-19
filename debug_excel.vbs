' debug_excel.vbs - SHOW ALL EXCEL INSTANCES
Option Explicit
Dim xlApp, wb, i, instances
On Error Resume Next

instances = 0
Set xlApp = GetObject(, "Excel.Application")
If Err.Number = 0 Then
    WScript.Echo "MAIN EXCEL INSTANCE:"
    WScript.Echo "  Workbooks (" & xlApp.Workbooks.Count & "):"
    For i = 1 To xlApp.Workbooks.Count
        WScript.Echo "    - " & xlApp.Workbooks(i).Name
    Next
    instances = instances + 1
End If
Err.Clear

WScript.Echo ""
WScript.Echo "TOTAL Excel instances: " & instances
WScript.Echo "Press OK to check manually..."
MsgBox "Check Task Manager for Excel.exe", vbInformation