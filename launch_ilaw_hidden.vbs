Set shell = CreateObject("WScript.Shell")
appFolder = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.Run Chr(34) & appFolder & "\launch_ilaw.bat" & Chr(34), 0, False
