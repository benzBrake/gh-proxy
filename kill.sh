#!/bin/bash
# 获取脚本所在目录的绝对路径
script_dir=$(dirname "$(readlink -f "$0")")
# 要结束的进程名
process_name="python $script_dir/app/main.py"

# 使用 pkill 结束进程
pkill -f "$process_name"

echo "进程 $process_name 已结束。"
