#!/bin/bash
# 获取脚本所在目录的绝对路径
script_dir=$(dirname "$(readlink -f "$0")")
if screen -list | grep -q "ghproxy"; then
    echo "Screen session 'ghproxy' is already running."
else
    if [ -f "$script_dir/run_app.sh" ]; then
    screen -dmS ghproxy -- "$script_dir/run_app.sh" --foreground
    echo "Started 'run_app.sh' in a new screen session 'ghproxy'."
    fi
fi