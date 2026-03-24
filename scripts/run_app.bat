@echo off
REM 设置控制台编码为 UTF-8
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ========================================
REM gh-proxy Windows 启动脚本
REM 使用 uv 进行依赖管理
REM ========================================

REM 配置参数
set app_directory=app
set app_script=main.py
set venv_dir=venv
set log_file=gh-proxy.log

REM 设置环境变量
set "ENABLE_JSDELIVR=0"
set "JSDELIVR_MIRROR=cdn.jsdelivr.net"
set "SIZE_LIMIT=1072668082176"
set "HOST=0.0.0.0"
set "PORT=8082"
set "ASSET_URL=https://benzbrake.github.io/gh-proxy"

REM 检测 Python 命令
where python >nul 2>&1
if %errorlevel% equ 0 (
    set python_cmd=python
    goto :check_venv
)

where python3 >nul 2>&1
if %errorlevel% equ 0 (
    set python_cmd=python3
    goto :check_venv
)

echo 错误：未找到 Python，请先安装 Python 3.12+
pause
exit /b 1

:check_venv
REM 检查虚拟环境是否存在
if exist ".venv\Scripts\activate.bat" (
    echo 虚拟环境已存在：.venv
    goto :activate_venv
)

if exist "%venv_dir%\Scripts\activate.bat" (
    echo 虚拟环境已存在：%venv_dir%
    goto :activate_venv
)

REM 虚拟环境不存在，创建虚拟环境
echo 虚拟环境不存在，正在创建...

REM 检查 uv 是否安装
where uv >nul 2>&1
if %errorlevel% equ 0 (
    echo 使用 uv 创建虚拟环境...
    uv venv
    goto :activate_venv
)

REM uv 未安装，询问是否安装
echo 未检测到 uv，是否现在安装？(Y/N)
set /p install_uv=

if /i "%install_uv%"=="Y" (
    echo 正在安装 uv...
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    if %errorlevel% neq 0 (
        echo uv 安装失败，尝试使用 venv...
        goto :use_venv
    )
    echo 请重新运行此脚本
    pause
    exit /b 0
) else (
    goto :use_venv
)

:use_venv
REM 使用 Python 内置 venv
echo 使用 !python_cmd! -m venv 创建虚拟环境...
!python_cmd! -m venv %venv_dir%

:activate_venv
REM 切换到项目根目录
cd /d "%~dp0.."

REM 激活虚拟环境
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    call %venv_dir%\Scripts\activate.bat
)

REM 安装依赖
echo 正在安装依赖...

where uv >nul 2>&1
if %errorlevel% equ 0 (
    echo 使用 uv 同步依赖...
    uv sync
    if %errorlevel% neq 0 (
        echo uv sync 失败，尝试使用 pip...
        goto :use_pip
    )
) else (
    :use_pip
    echo 使用 pip 安装依赖...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo 依赖安装失败
        pause
        exit /b 1
    )
)

REM 启动应用
echo 正在启动 gh-proxy...
echo.
echo ========================================
echo gh-proxy 正在运行
echo 访问地址：http://localhost:8082
echo 按 Ctrl+C 停止服务
echo ========================================
echo.

where uv >nul 2>&1
if %errorlevel% equ 0 (
    uv run python %app_directory%/%app_script%
) else (
    python %app_directory%/%app_script%
)

endlocal
