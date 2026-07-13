#!/bin/bash

script_dir=$(dirname "$(readlink -f "$0")")
project_root=$(cd "$script_dir/.." && pwd)
process_pattern="$project_root/app/main.py"

if pkill -f "$process_pattern"; then
    echo "已结束进程: $process_pattern"
else
    echo "未找到进程: $process_pattern"
fi
