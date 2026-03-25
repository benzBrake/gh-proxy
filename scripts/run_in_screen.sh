#!/bin/bash

script_dir=$(dirname "$(readlink -f "$0")")
run_app_script="$script_dir/run_app.sh"

if ! command -v screen >/dev/null 2>&1; then
    echo "Error: 'screen' is not installed."
    exit 1
fi

if screen -list | grep -Eq '[0-9]+\.ghproxy[[:space:]]'; then
    echo "Screen session 'ghproxy' is already running."
    exit 0
fi

if [ ! -f "$run_app_script" ]; then
    echo "Error: cannot find $run_app_script"
    exit 1
fi

screen -dmS ghproxy bash "$run_app_script" --foreground
echo "Started 'run_app.sh' in a new screen session 'ghproxy'."
