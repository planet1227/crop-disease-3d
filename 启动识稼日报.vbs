Dim fso, sh, py, sp
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

' 用脚本自己所在的目录，解压到哪都能跑
sp = fso.GetParentFolderName(WScript.ScriptFullName) & "\start.py"

py = "C:\Users\planet\miniconda3\envs\nongda\pythonw.exe"
If Not fso.FileExists(py) Then py = "pythonw.exe"

' 0 = 隐藏窗口，False = 不等待
sh.Run """" & py & """ """ & sp & """ --quiet", 0, False
