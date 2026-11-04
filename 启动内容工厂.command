#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo '请先从 https://www.python.org/downloads/macos/ 安装 Python 3.10 或更高版本。'
  read -r -p '按回车关闭窗口…'
  exit 1
fi
python3 mac_launcher.py
