Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = appDir

venvPythonw = fso.BuildPath(fso.GetParentFolderName(appDir), ".venv\Scripts\pythonw.exe")
If Not fso.FileExists(venvPythonw) Then
  venvPythonw = fso.BuildPath(appDir, ".venv\Scripts\pythonw.exe")
End If

If Not fso.FileExists(venvPythonw) Then
  MsgBox "Could not find virtual environment pythonw.exe for the migrated project.", 16, "Inventory System"
  WScript.Quit 1
End If

' Stop server silently
shell.Run """" & venvPythonw & """ ""stop_local.py""", 0, False
