Dim fso, sh, py, sp
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

' 以脚本自身所在目录为准，解压到哪都能跑
sp = fso.GetParentFolderName(WScript.ScriptFullName) & "\start.py"

' 优先用包里自带的绿色 Python，没有再用系统的
py = fso.GetParentFolderName(WScript.ScriptFullName) & "\runtime\pythonw.exe"
If Not fso.FileExists(py) Then py = "pythonw.exe"

' 0 = 不显示窗口，False = 不等待
sh.Run """" & py & """ """ & sp & """ --quiet", 0, False
