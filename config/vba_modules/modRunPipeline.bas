Attribute VB_Name = "modRunPipeline"
Option Explicit

' CLL Data Pipeline Trigger for Excel
' Import this module via VBA Editor (Alt+F11 > File > Import)
' Then assign RunPipeline to a button on the Pipeline Metadata sheet
'
' SETUP: Place this workbook inside the "Data Pipeline tool" folder,
' or adjust GetPipelineDir() to point to the correct location.

Private Function GetPipelineDir() As String
    ' Detect pipeline directory relative to this workbook
    Dim wbPath As String
    wbPath = ThisWorkbook.Path
    
    ' If workbook is inside the pipeline folder, use it directly
    If Dir(wbPath & "/run_tool.py") <> "" Then
        GetPipelineDir = wbPath
    ' If workbook is in a subfolder (e.g. manual extract), go up
    ElseIf Dir(wbPath & "/../../run_tool.py") <> "" Then
        GetPipelineDir = wbPath & "/../.."
    ' If workbook is in Client presentation folder, look for sibling
    ElseIf Dir(wbPath & "/../Data Pipeline tool/run_tool.py") <> "" Then
        GetPipelineDir = wbPath & "/../Data Pipeline tool"
    Else
        GetPipelineDir = ""
    End If
End Function

Private Function GetPythonPath(pipelineDir As String) As String
    ' Try common Python locations
    If Dir(pipelineDir & "/.venv/bin/python3") <> "" Then
        GetPythonPath = pipelineDir & "/.venv/bin/python3"
    ElseIf Dir(pipelineDir & "/.venv/Scripts/python.exe") <> "" Then
        GetPythonPath = pipelineDir & "/.venv/Scripts/python.exe"
    Else
        ' Fall back to system Python
        #If Mac Then
            GetPythonPath = "/usr/local/bin/python3"
        #Else
            GetPythonPath = "python"
        #End If
    End If
End Function

Sub RunPipeline()
    Dim pipelineDir As String
    pipelineDir = GetPipelineDir()
    
    If pipelineDir = "" Then
        MsgBox "Could not find the Data Pipeline tool folder." & vbCr & vbCr & _
            "Place this workbook inside the pipeline folder," & vbCr & _
            "or ensure run_tool.py is accessible from the workbook location.", _
            vbExclamation, "Pipeline Not Found"
        Exit Sub
    End If
    
    Dim pythonPath As String
    pythonPath = GetPythonPath(pipelineDir)
    
    Dim answer As VbMsgBoxResult
    answer = MsgBox("Run CLL Data Pipeline?" & vbCr & vbCr & _
        "Pipeline: " & pipelineDir & vbCr & _
        "Python: " & pythonPath & vbCr & vbCr & _
        "Estimated time: 2-5 minutes.", vbYesNo + vbQuestion, "Data Pipeline")
    If answer = vbNo Then Exit Sub

    Dim startTime As Double
    startTime = Timer

    Dim cmd As String
    cmd = pythonPath & " """ & pipelineDir & "/run_tool.py"" --indication CLL --country US"

    ' Update Pipeline Metadata sheet
    Dim wsMeta As Worksheet
    On Error Resume Next
    Set wsMeta = ThisWorkbook.Sheets("Pipeline Metadata")
    On Error GoTo 0
    If wsMeta Is Nothing Then
        MsgBox "Pipeline Metadata sheet not found!", vbExclamation
        Exit Sub
    End If

    wsMeta.Range("B4").Value = Now()
    wsMeta.Range("B10").Value = "Running..."
    Application.ScreenUpdating = False

    Dim result As String
    #If Mac Then
        On Error GoTo PipelineError
        result = MacScript("do shell script """ & Replace(cmd, """", "\"&"""") & " 2>&1""")
    #Else
        On Error GoTo PipelineError
        Dim wsh As Object
        Set wsh = CreateObject("WScript.Shell")
        Dim exec As Object
        Set exec = wsh.exec(cmd)
        Do While exec.Status = 0
            DoEvents
        Loop
        result = exec.StdOut.ReadAll
    #End If

    ' Import evidence CSV
    Call RefreshEvidenceData

    ' Update metadata
    Dim elapsed As Double
    elapsed = Timer - startTime
    wsMeta.Range("B10").Value = "Success"
    wsMeta.Range("B11").Value = Round(elapsed, 1) & " seconds"
    wsMeta.Range("B5").Value = cmd

    ' Append to run history (row 16+)
    Dim histRow As Long
    histRow = wsMeta.Cells(wsMeta.Rows.Count, "A").End(xlUp).Row + 1
    If histRow < 16 Then histRow = 16
    wsMeta.Cells(histRow, 1).Value = histRow - 15
    wsMeta.Cells(histRow, 2).Value = Now()
    wsMeta.Cells(histRow, 3).Value = wsMeta.Range("B8").Value
    wsMeta.Cells(histRow, 4).Value = Round(elapsed, 1)
    wsMeta.Cells(histRow, 5).Value = "Success"

    Application.ScreenUpdating = True
    MsgBox "Pipeline complete!" & vbCr & _
        "Duration: " & Round(elapsed, 1) & " seconds" & vbCr & _
        "Records: " & wsMeta.Range("B8").Value, vbInformation, "Done"
    Exit Sub

PipelineError:
    Application.ScreenUpdating = True
    wsMeta.Range("B10").Value = "Error: " & Err.Description
    Dim elapsedErr As Double
    elapsedErr = Timer - startTime
    wsMeta.Range("B11").Value = Round(elapsedErr, 1) & " seconds"

    Dim errRow As Long
    errRow = wsMeta.Cells(wsMeta.Rows.Count, "A").End(xlUp).Row + 1
    If errRow < 16 Then errRow = 16
    wsMeta.Cells(errRow, 1).Value = errRow - 15
    wsMeta.Cells(errRow, 2).Value = Now()
    wsMeta.Cells(errRow, 4).Value = Round(elapsedErr, 1)
    wsMeta.Cells(errRow, 5).Value = "Error: " & Err.Description

    MsgBox "Pipeline failed:" & vbCr & Err.Description, vbCritical, "Error"
End Sub

Sub RefreshEvidenceData()
    Dim pipelineDir As String
    pipelineDir = GetPipelineDir()
    If pipelineDir = "" Then Exit Sub
    
    Dim csvPath As String
    csvPath = pipelineDir & "/output/evidence_by_metric_CLL_(Chronic_Lymphocytic_Leukemia)_US.csv"

    Dim wsEv As Worksheet
    On Error Resume Next
    Set wsEv = ThisWorkbook.Sheets("Evidence Data")
    On Error GoTo 0
    If wsEv Is Nothing Then
        MsgBox "Evidence Data sheet not found!", vbExclamation
        Exit Sub
    End If

    ' Clear existing data (keep headers in rows 1-3)
    Dim lastRow As Long
    lastRow = wsEv.Cells(wsEv.Rows.Count, "A").End(xlUp).Row
    If lastRow > 3 Then wsEv.Range("A4:L" & lastRow).ClearContents

    ' Read CSV and populate
    Dim fNum As Integer, line As String, parts() As String
    Dim r As Long: r = 4
    fNum = FreeFile

    On Error GoTo CSVError
    Open csvPath For Input As #fNum

    Dim headerLine As String
    Line Input #fNum, headerLine  ' skip header

    Do While Not EOF(fNum)
        Line Input #fNum, line
        If Len(Trim(line)) > 0 Then
            parts = Split(line, ",")
            If UBound(parts) >= 5 Then
                wsEv.Cells(r, 1).Value = parts(0)  ' Category
                wsEv.Cells(r, 2).Value = parts(1)  ' Metric
                wsEv.Cells(r, 3).Value = parts(2)  ' Value
                wsEv.Cells(r, 4).Value = parts(3)  ' Unit
                wsEv.Cells(r, 5).Value = parts(4)  ' Source
                wsEv.Cells(r, 6).Value = parts(5)  ' Year
                If UBound(parts) >= 6 Then wsEv.Cells(r, 7).Value = parts(6)  ' Geography
                If UBound(parts) >= 9 Then wsEv.Cells(r, 11).Value = parts(9)  ' Source Tier
                If UBound(parts) >= 10 Then wsEv.Cells(r, 12).Value = parts(10)  ' Confidence
                r = r + 1
            End If
        End If
    Loop
    Close #fNum

    ' Update record count in Pipeline Metadata
    Dim wsMeta As Worksheet
    Set wsMeta = ThisWorkbook.Sheets("Pipeline Metadata")
    wsMeta.Range("B8").Value = r - 4

    ' Update Evidence Data subtitle
    wsEv.Range("A2").Value = "Total data points: " & (r - 4) & " | Updated: " & Format(Now(), "yyyy-mm-dd hh:mm")
    Exit Sub

CSVError:
    Close #fNum
    MsgBox "Could not read CSV file:" & vbCr & csvPath & vbCr & vbCr & Err.Description, vbExclamation, "CSV Import Error"
End Sub
