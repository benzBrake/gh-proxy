#!/bin/bash
# 获取脚本所在目录的绝对路径
script_dir=$(dirname "$(readlink -f "$0")")

# 设置环境变量
export ENABLE_JSDELIVR=0
export JSDELIVR_MIRROR="cdn.jsdelivr.net"
# 默认超过 999MB 的返回源链接
export SIZE_LIMIT=1072668082176
export HOST="0.0.0.0"
export PORT=8082
export ASSET_URL="https://hunshcn.github.io/gh-proxy"

# 脚本参数
venv_dir="$script_dir/venv"
requirements_file="$script_dir/requirements.txt"
app_directory="$script_dir/app"
app_script="main.py"
log_file="$script_dir/app.log"

proc_list() {
    # 检测进程是否已经运行
    echo Process List:
    ps -ef | grep -v grep | grep "$app_directory/$app_script"
    if [ $? -eq 0 ]; then
        exit
    fi
}

# 检查虚拟环境是否存在
if [ ! -d "$venv_dir" ]; then
    echo "虚拟环境不存在，正在创建..."

    # 安装 Python、pip 和 venv
    if [ "$EUID" -ne 0 ]; then
        # 不是 root 用户，使用 sudo
        sudo_command="sudo"
    fi

    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        $sudo_command apt-get update
        $sudo_command apt-get install -y python3 python3-pip python3-venv
    elif command -v yum &> /dev/null; then
        # CentOS
        $sudo_command yum install -y python3 python3-pip python3-venv
    elif command -v apk &> /dev/null; then
        # Alpine
        $sudo_command apk add python3 py3-pip py3-venv
    else
        echo "不支持的系统。"
        exit 1
    fi
    
    # 创建虚拟环境
    python3 -m venv "$venv_dir"

    echo "虚拟环境已创建。"
fi

proc_list

# 激活虚拟环境
source "$venv_dir/bin/activate"

# 安装依赖项
pip install -r "$requirements_file"

# 使用 screen 启动 Flask 应用程序
nohup python "$app_directory/$app_script" >> "$log_file" 2>&1 &

proc_list
