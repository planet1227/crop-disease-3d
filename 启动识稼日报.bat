@echo off
chcp 936 >nul
title 识稼日报 · 启动器
cd /d "%~dp0"

set PY=C:\Users\planet\miniconda3\envs\nongda\python.exe
if not exist "%PY%" set PY=python

"%PY%" start.py
if errorlevel 1 pause
