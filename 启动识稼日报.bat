@echo off
chcp 936 >nul
title 识稼日报 · 启动器
cd /d "%~dp0"

set "PY="
set "PYARGS="
set "ISRUNTIME="

rem ===== 1. 包内自带的绿色运行时，优先用它 =====
if not exist "%~dp0runtime\python.exe" goto scan
"%~dp0runtime\python.exe" -c "import sys" >nul 2>nul
if errorlevel 1 goto scan
set PY="%~dp0runtime\python.exe"
set "ISRUNTIME=1"
goto havepy

rem ===== 2. 没有运行时，再找本机装的 Python =====
rem     不能只用 where 判断，微软商店的占位符会骗人，必须真跑一次
:scan
for %%P in (
    "%LocalAppData%\Programs\Python\Python313\python.exe"
    "%LocalAppData%\Programs\Python\Python312\python.exe"
    "%LocalAppData%\Programs\Python\Python311\python.exe"
    "%LocalAppData%\Programs\Python\Python310\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "%ProgramFiles%\Python313\python.exe"
    "%ProgramFiles%\Python312\python.exe"
    "%ProgramFiles%\Python311\python.exe"
    "%ProgramFiles%\Python310\python.exe"
    "C:\Users\%USERNAME%\miniconda3\python.exe"
    "C:\Users\%USERNAME%\anaconda3\python.exe"
    "C:\ProgramData\miniconda3\python.exe"
) do (
    if not defined PY if exist "%%~P" (
        "%%~P" -c "import sys" >nul 2>nul
        if not errorlevel 1 set PY="%%~P"
    )
)

if defined PY goto havepy

py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 (
    set "PY=py"
    set "PYARGS=-3"
    goto havepy
)

python -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY=python"

if not defined PY goto nopython

rem ===== 3. 依赖检查 =====
:havepy
%PY% %PYARGS% -c "import fastapi, uvicorn, PIL, requests, multipart" >nul 2>nul
if not errorlevel 1 goto run

if defined ISRUNTIME goto broken

rem 用的是本机 Python，缺依赖时只问、不擅自装，免得动到别人的系统环境
echo.
echo   这台电脑的 Python 缺运行依赖。
echo   现在用的是：%PY% %PYARGS%
echo.
set "ANS="
set /p "ANS=  要现在自动安装到这里吗？(Y/N) "
if /i not "%ANS%"=="Y" goto nodeps

%PY% %PYARGS% -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto pipfail
%PY% %PYARGS% -c "import fastapi, uvicorn, PIL, requests, multipart" >nul 2>nul
if errorlevel 1 goto pipfail
goto run

:nodeps
echo.
echo   那就先不装。要跑起来，二选一：
echo     1. 在本文件夹里执行：%PY% %PYARGS% -m pip install -r requirements.txt
echo     2. 检查包里的 runtime 文件夹是否完整（那是自带的绿色 Python，不用装）
echo.
pause
exit /b 1

:run
echo.
echo   正在启动「识稼日报」……
echo   浏览器大约 3 秒后自动打开；关掉这个窗口，服务就停了。
echo.
%PY% %PYARGS% "%~dp0start.py"
if errorlevel 1 pause
exit /b 0

:broken
echo.
echo   包里的运行环境不完整，多半是解压时被杀毒软件拦掉了。
echo   请先退出杀毒软件，把压缩包重新解压一次，再双击本文件。
echo.
pause
exit /b 1

:pipfail
echo.
echo   依赖没装上，一般是网络问题。手动再试一次：
echo     %PY% %PYARGS% -m pip install -r "%~dp0requirements.txt"
echo.
pause
exit /b 1

:nopython
echo.
echo   ================================================
echo    这台电脑还没装 Python，而包里也没找到 runtime。
echo.
echo    最省事：重新完整解压整个压缩包，runtime 文件夹
echo    必须和本文件在同一层。
echo.
echo    要自己装 Python 的话：
echo      1. 打开 https://www.python.org/downloads/
echo      2. 下载 Python 3.10 或更高版本
echo      3. 安装时务必勾选 "Add Python to PATH"
echo      4. 关掉本窗口，重新双击运行
echo   ================================================
echo.
pause
exit /b 1
