#!/bin/bash
# 获取脚本所在目录的绝对路径
script_dir=$(dirname "$(readlink -f "$0")")

# 设置环境变量
export ENABLE_JSDELIVR=${ENABLE_JSDELIVR-0}
export JSDELIVR_MIRROR=${JSDELIVR_MIRROR-cdn.jsdelivr.net}
# 默认超过 999MB 的返回源链接
export SIZE_LIMIT=${SIZE_LIMIT-1072668082176}
export HOST=${HOST-0.0.0.0}
export PORT=${PORT-8082}
export ASSET_URL=${ASSET_URL-https://hunshcn.github.io/gh-proxy}

# 脚本参数
venv_dir="$script_dir/venv"
requirements_file="$script_dir/requirements.txt"
app_directory="$script_dir/app"
app_script="main.py"
log_file="$script_dir/app.log"

# 是否后台运行标志
run_in_background=true
# 是否开启调试模式标志
debug_mode=false
# 是否安装软件包标志
install_packages=true

# 检查参数
for arg in "$@"; do
    case "$arg" in
        --forceground)
            run_in_background=false
            ;;
        --debug)
            export DEBUG_MODE=1
            run_in_background=false  # 强制前台运行
            ;;
        --no-root)
            install_packages=false
            ;;
    esac
done

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

    if [ "$install_packages" == true ]; then
      # 安装 Python、pip 和 venv
      if [ "$EUID" -ne 0 ] && [ "$install_packages" == true ]; then
          # 不是 root 用户，使用 sudo
          sudo_command="sudo"
      else
          sudo_command=""
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


# 启动 Flask 应用程序
if [ "$run_in_background" == true ]; then
    nohup python "$app_directory/$app_script" >> "$log_file" 2>&1 &
    proc_list
else
    python "$app_directory/$app_script"
fi
