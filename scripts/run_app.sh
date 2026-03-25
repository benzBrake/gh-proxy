#!/bin/bash

script_dir=$(dirname "$(readlink -f "$0")")
project_root=$(cd "$script_dir/.." && pwd)
cd "$project_root" || exit 1

# 设置环境变量
export ENABLE_JSDELIVR=${ENABLE_JSDELIVR-0}
export JSDELIVR_MIRROR=${JSDELIVR_MIRROR-cdn.jsdelivr.net}
# 默认超过 999MB 的返回源链接
export SIZE_LIMIT=${SIZE_LIMIT-1072668082176}
export HOST=${HOST-0.0.0.0}
export PORT=${PORT-8082}
export ASSET_URL=${ASSET_URL-https://benzbrake.github.io/gh-proxy}
export API_PROXY=${API_PROXY-}
export API_PROXY_SECONDARY=${API_PROXY_SECONDARY-}
export API_PROXY_RETRIES=${API_PROXY_RETRIES-3}
export API_PROXY_TIMEOUT=${API_PROXY_TIMEOUT-15}

# 脚本参数
venv_dir="$project_root/.venv"
requirements_file="$project_root/requirements.txt"
app_directory="$project_root/app"
app_script="main.py"
log_file="$project_root/gh-proxy.log"

# 是否后台运行标志
run_in_background=true
# 是否安装软件包标志
install_packages=true

# 检查参数
for arg in "$@"; do
    case "$arg" in
    --foreground)
        run_in_background=false
        ;;
    --debug)
        export DEBUG_MODE=1
        run_in_background=false # 强制前台运行
        ;;
    --no-root)
        install_packages=false
        ;;
    esac
done

proc_list() {
    # 检测进程是否已经运行
    echo Process List:
    ps aux | grep -v grep | grep "$app_directory/$app_script"
    if [ $? -eq 0 ]; then
        exit
    fi
}

# 检测 Python 命令
python_cmd=$(command -v python3 || command -v python)

# 检查虚拟环境是否存在
if [ ! -d "$venv_dir" ]; then
    echo "虚拟环境不存在，正在创建..."

    # 优先使用 uv
    if command -v uv &> /dev/null; then
        echo "使用 uv 创建虚拟环境..."
        uv venv "$venv_dir"
    elif command -v python3 &> /dev/null; then
        echo "使用 python3 -m venv 创建虚拟环境..."
        python3 -m venv "$venv_dir"
    elif command -v python &> /dev/null; then
        echo "使用 python -m venv 创建虚拟环境..."
        python -m venv "$venv_dir"
    else
        echo "错误：未找到 Python 或 uv"

        if [ "$install_packages" == true ]; then
            # 尝试安装 Python
            if [ "$EUID" -ne 0 ] && [ "$install_packages" == true ]; then
                sudo_command="sudo"
            else
                sudo_command=""
            fi

            if command -v apt-get &>/dev/null; then
                # Debian/Ubuntu
                $sudo_command apt-get update
                $sudo_command apt-get install -y python3 python3-pip python3-venv
            elif command -v yum &>/dev/null; then
                # CentOS
                $sudo_command yum install -y python3 python3-pip python3-venv
            elif command -v apk &>/dev/null; then
                # Alpine
                $sudo_command apk add python3 py3-pip py3-venv
            else
                echo "不支持的系统。"
                exit 1
            fi

            # 创建虚拟环境
            python3 -m venv "$venv_dir"
        else
            exit 1
        fi
    fi
    echo "虚拟环境已创建。"
fi

proc_list

# 激活虚拟环境
if [ -f "$venv_dir/bin/activate" ]; then
    source "$venv_dir/bin/activate"
fi

# 安装/更新依赖
echo "正在安装依赖..."

if command -v uv &> /dev/null; then
    echo "使用 uv 同步依赖..."
    uv sync
elif command -v pip &> /dev/null; then
    echo "使用 pip 安装依赖..."
    pip install -r "$requirements_file"
else
    echo "错误：未找到 uv 或 pip"
    exit 1
fi

# 启动 Flask 应用程序
if [ "$run_in_background" == true ]; then
    if command -v uv &> /dev/null; then
        nohup uv run python "$app_directory/$app_script" >>"$log_file" 2>&1 &
    else
        nohup python "$app_directory/$app_script" >>"$log_file" 2>&1 &
    fi
    proc_list
else
    if command -v uv &> /dev/null; then
        uv run python "$app_directory/$app_script"
    else
        python "$app_directory/$app_script"
    fi
fi
