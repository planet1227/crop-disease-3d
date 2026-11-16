Dim fso, sh, py, sp
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

py = "C:\Users\planet\miniconda3\envs\nongda\pythonw.exe"
sp = "C:\Users\planet\Desktop\ai_dasai\start.py"

If Not fso.FileExists(py) Then py = "pythonw.exe"

' 0 = 隐藏窗口，False = 不等它结束
sh.Run """" & py & """ """ & sp & """ --quiet", 0, False
