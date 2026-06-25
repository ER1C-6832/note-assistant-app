Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
bat = fso.BuildPath(scriptDir, "start_voice_prewarm.bat")
shell.Run """" & bat & """", 0, False
