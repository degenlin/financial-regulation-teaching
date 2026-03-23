@echo off
chcp 65001 >nul
title 金融监管教学实验系统
color 1F
cls

echo.
echo  ============================================
echo    金融监管教学实验系统  启动中...
echo  ============================================
echo.
echo    教师账号: teacher / teacher123
echo    学生可自行注册账号
echo.

:: 切换到教学系统目录
cd /d "%~dp0教学系统"

:: 查找 Python（兼容 python / python3 / py）
set PYTHON=
where python >nul 2>&1 && set PYTHON=python
if "%PYTHON%"=="" (
    where python3 >nul 2>&1 && set PYTHON=python3
)
if "%PYTHON%"=="" (
    where py >nul 2>&1 && set PYTHON=py
)
if "%PYTHON%"=="" (
    echo  [错误] 未找到 Python，请先安装 Python 3.8+
    echo  下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo  已找到 Python: %PYTHON%

:: 检查并安装 Flask
%PYTHON% -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo  正在安装 Flask...
    %PYTHON% -m pip install flask -q
    echo  Flask 安装完成
)

:: 自动打开浏览器（延迟2秒）
start "" cmd /c "timeout /t 2 >nul && start http://127.0.0.1:5000"

echo  服务启动中，浏览器将自动打开...
echo  如未自动打开，请访问: http://127.0.0.1:5000
echo  局域网其他电脑可访问: http://本机IP:5000
echo  按 Ctrl+C 停止服务
echo  ============================================
echo.

%PYTHON% app.py

echo.
echo  服务已停止。
pause
