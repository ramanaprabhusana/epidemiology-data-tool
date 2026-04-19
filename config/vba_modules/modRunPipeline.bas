Attribute VB_Name = "modRunPipeline"
Option Explicit

' Multi-Indication Data Pipeline Trigger for Excel (v5.2 edition)
' Import this module via VBA Editor (Alt+F11 > File > Import)
'
' Public entry points for buttons on the Control Panel sheet:
'   - RefreshAll(): runs pipeline for all 6 indications + patches workbook
'   - RefreshIndication("CLL"): runs pipeline for a single indication + patches workbook
'   - RefreshCLL / RefreshHodgkin / RefreshNonHodgkin / RefreshGastric / RefreshOvarian / RefreshProstate
'     convenience wrappers for button assignment
'   - RunPipeline(): legacy single-indication (CLL) trigger, kept for back-compat
'
' SETUP: Place this workbook inside the "Data Pipeline tool" folder,
' or adjust GetPipelineDir() to point to the correct location. The usual layout is:
'   <project root>/
'     Data Pipeline tool/          ← this module's scripts live here
'     Client presentation/
'       CLL_Consolidated_Forecast_Model_v5.2.xlsx   ← this workbook

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
    csvPath = pipelineDir & "/output/evidence_by_metric_CLL_US.csv"

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

' ─────────────────────────────────────────────────────────────────────────────
' MULTI-INDICATION REFRESH (v5.2 workflow)
' ─────────────────────────────────────────────────────────────────────────────
' These subs shell out to run_all_indications.py which, in turn:
'   1. Runs src/pipeline/runner.py for each indication (SEER/GLOBOCAN/WHO pulls)
'   2. Writes pipeline outputs under output/ (evidence_by_metric_<suffix>.csv, etc.)
'   3. Builds output/consolidated_run.xlsx and output/run_manifest.json
'   4. Invokes refresh_workbook.py which patches this workbook's
'      Lookup Tables (Model Inputs rows 5-10) + Evidence sheets + Pipeline Metadata
'   USER EDITS ON FORECAST / SUMMARY DASHBOARD / SCENARIOS ARE NEVER TOUCHED.

Public Sub RefreshAll()
    Call DoMultiRefresh("")   ' empty string → all 6 indications (run_all_indications default)
End Sub

Public Sub RefreshIndication(ind As String)
    If Len(Trim(ind)) = 0 Then
        MsgBox "RefreshIndication requires an indication name (e.g. 'CLL' or 'Hodgkin Lymphoma').", vbExclamation
        Exit Sub
    End If
    Call DoMultiRefresh(ind)
End Sub

' Convenience wrappers: assign these directly to shape buttons on Control Panel
' Use full pipeline labels for Hodgkin / NHL so they match run_all_indications.py / INDICATION_SUFFIX.
Public Sub RefreshCLL():         Call DoMultiRefresh("CLL"):                   End Sub
Public Sub RefreshHodgkin():     Call DoMultiRefresh("Hodgkin Lymphoma"):     End Sub
Public Sub RefreshNonHodgkin():  Call DoMultiRefresh("Non-Hodgkin Lymphoma"): End Sub
Public Sub RefreshGastric():     Call DoMultiRefresh("Gastric"):               End Sub
Public Sub RefreshOvarian():     Call DoMultiRefresh("Ovarian"):               End Sub
Public Sub RefreshProstate():    Call DoMultiRefresh("Prostate"):             End Sub

Private Sub DoMultiRefresh(ind As String)
    Dim pipelineDir As String
    pipelineDir = GetPipelineDir()
    If pipelineDir = "" Then
        MsgBox "Could not find the Data Pipeline tool folder." & vbCr & vbCr & _
            "Expected layout:" & vbCr & _
            "  <project>/Data Pipeline tool/run_all_indications.py" & vbCr & _
            "  <project>/Client presentation/CLL_Consolidated_Forecast_Model_v5.2.xlsx", _
            vbExclamation, "Pipeline Not Found"
        Exit Sub
    End If

    Dim batchScript As String
    batchScript = pipelineDir & "/run_all_indications.py"
    If Dir(batchScript) = "" Then
        MsgBox "run_all_indications.py not found at:" & vbCr & batchScript, vbExclamation
        Exit Sub
    End If

    Dim pythonPath As String
    pythonPath = GetPythonPath(pipelineDir)

    Dim title As String, prompt As String
    If Len(ind) = 0 Then
        title = "Refresh All Indications"
        prompt = "Run the Data Pipeline for ALL 6 indications (CLL, Hodgkin Lymphoma, Non-Hodgkin Lymphoma, Gastric, Ovarian, Prostate)?" & vbCr & vbCr
    Else
        title = "Refresh " & ind
        prompt = "Run the Data Pipeline for " & ind & " only?" & vbCr & vbCr
    End If
    prompt = prompt & "Pipeline: " & pipelineDir & vbCr & _
                      "Python:   " & pythonPath & vbCr & _
                      "Workbook: " & ThisWorkbook.FullName & vbCr & vbCr & _
                      "This will update Lookup Tables, Evidence sheets, and Pipeline Metadata." & vbCr & _
                      "Forecast sheets, Summary Dashboard, and Scenarios are NOT touched." & vbCr & vbCr & _
                      "Estimated time: " & IIf(Len(ind) = 0, "10-20", "2-5") & " minutes."

    Dim answer As VbMsgBoxResult
    answer = MsgBox(prompt, vbYesNo + vbQuestion, title)
    If answer = vbNo Then Exit Sub

    ' Save + close so refresh_workbook.py can open it, then reopen after
    Dim wbPath As String, wbName As String
    wbPath = ThisWorkbook.FullName
    wbName = ThisWorkbook.Name

    If ThisWorkbook.Path = "" Then
        MsgBox "Please save this workbook before running the refresh.", vbExclamation
        Exit Sub
    End If
    ThisWorkbook.Save

    ' Build command line
    Dim cmd As String
    cmd = """" & pythonPath & """ """ & batchScript & """ --country US --workbook """ & wbPath & """"
    If Len(ind) > 0 Then
        cmd = cmd & " --indications """ & ind & """"
    End If

    Dim startTime As Double
    startTime = Timer
    Application.ScreenUpdating = False
    Application.StatusBar = "Running pipeline for " & IIf(Len(ind) = 0, "all indications", ind) & "..."

    ' Run the shell command and wait for completion
    Dim ok As Boolean
    ok = ShellAndWait(cmd, pipelineDir)

    Application.StatusBar = False
    Application.ScreenUpdating = True

    Dim elapsed As Double
    elapsed = Timer - startTime

    If Not ok Then
        MsgBox "Pipeline run failed. Check terminal output / log files under:" & vbCr & _
               pipelineDir & "/output/", vbCritical, "Refresh Failed"
        Exit Sub
    End If

    ' refresh_workbook.py saved changes to the file on disk. We need to reopen
    ' this workbook to see them. Close without saving (we already saved above
    ' and the on-disk copy is the fresh one).
    Application.DisplayAlerts = False
    ThisWorkbook.Close SaveChanges:=False
    Application.DisplayAlerts = True

    Workbooks.Open Filename:=wbPath
    MsgBox "Refresh complete." & vbCr & _
           "Duration: " & Format(elapsed, "0.0") & " seconds" & vbCr & vbCr & _
           "Review Pipeline Metadata sheet for updated run details.", _
           vbInformation, "Done"
End Sub

Private Function ShellAndWait(cmd As String, workDir As String) As Boolean
    On Error GoTo RunErr
    #If Mac Then
        ' AppleScript chains: cd to pipeline dir, then run the command, capture exit status
        Dim applCmd As String
        applCmd = "do shell script ""cd '" & workDir & "' && " & _
                  Replace(Replace(cmd, "\", "\\"), """", "\""") & " 2>&1"""
        Dim res As String
        res = MacScript(applCmd)
        ShellAndWait = True
    #Else
        ' Windows: use WScript.Shell and wait for completion
        Dim wsh As Object
        Set wsh = CreateObject("WScript.Shell")
        wsh.CurrentDirectory = workDir
        Dim rc As Long
        rc = wsh.Run("cmd /c " & cmd, 1, True)   ' 1 = show window, True = wait
        ShellAndWait = (rc = 0)
    #End If
    Exit Function

RunErr:
    ShellAndWait = False
End Function
