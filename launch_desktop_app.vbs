Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Check if server is already running by querying localhost:8000
On Error Resume Next
Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
http.open "GET", "http://127.0.0.1:8000/api/info", False
http.setTimeouts 500, 500, 500, 500
http.send

Dim serverProc
Set serverProc = Nothing

If Err.Number <> 0 Then
    ' Server is not running, start it silently with pythonw.exe
    WshShell.CurrentDirectory = scriptDir
    Set serverProc = WshShell.Exec(Chr(34) & scriptDir & "\.venv\Scripts\pythonw.exe" & Chr(34) & " -m uvicorn web.app:app --host 0.0.0.0 --port 8000")
    WScript.Sleep 1500
End If
On Error GoTo 0

' Determine browser path for standalone app window
edgePath = WshShell.ExpandEnvironmentStrings("%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe")
chromePath = WshShell.ExpandEnvironmentStrings("%ProgramFiles%\Google\Chrome\Application\chrome.exe")
localAppData = WshShell.ExpandEnvironmentStrings("%LocalAppData%")
chromeUser = localAppData & "\Google\Chrome\Application\chrome.exe"

Dim appCmd
If fso.FileExists(edgePath) Then
    appCmd = Chr(34) & edgePath & Chr(34) & " --app=http://localhost:8000"
ElseIf fso.FileExists(chromePath) Then
    appCmd = Chr(34) & chromePath & Chr(34) & " --app=http://localhost:8000"
ElseIf fso.FileExists(chromeUser) Then
    appCmd = Chr(34) & chromeUser & Chr(34) & " --app=http://localhost:8000"
Else
    appCmd = "http://localhost:8000"
End If

' Launch standalone desktop app window and wait until closed
WshShell.Run appCmd, 1, True

' When user closes the app window, cleanly terminate the background server
If Not serverProc Is Nothing Then
    On Error Resume Next
    serverProc.Terminate
    On Error GoTo 0
End If
