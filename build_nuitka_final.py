#!/bin/bash
# Nuitka 打包脚本 (正式版本)
# 使用方法: 
# 1. 安装 Nuitka: pip install nuitka
# 2. 运行此脚本: python build_nuitka_final.py

import subprocess
import sys
import os

# Ensure UTF-8 console output on Windows CI
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def build_with_nuitka():
    """使用Nuitka构建可执行文件 - 正式版本 (一文件 + 独立目录输出)"""

    cache_dir = os.environ.get("CACHE_DIR", "nuitka-cache")

    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        f"--onefile-tempdir-spec={cache_dir}",
        "--standalone",
        "--assume-yes-for-downloads",
        "--windows-console-mode=disable",
        "--enable-plugin=tk-inter",
        "--include-data-dir=static=static",
        "--include-data-files=icon.ico=icon.ico",
        "--windows-icon-from-ico=icon.ico",
        "--include-module=webview.platforms.edgechromium",
        "--include-module=schedule",
        "--include-module=requests",
        "--include-module=pptx",
        "--include-module=json",
        "--include-module=threading",
        "--include-module=pathlib",
        "--include-module=pystray",
        "--include-module=PIL",
        "--include-module=socket",
        "--include-module=tempfile",
        "--include-module=winreg",
        "--include-module=logging",
        "--include-module=argparse",
        "--output-dir=dist_nuitka",
        "--output-filename=AutoHomework.exe",
        "main.py",
    ]

    print("Start building with Nuitka (onefile release)...")
    print("Command:", " ".join(nuitka_cmd))

    try:
        result = subprocess.run(nuitka_cmd, check=True, capture_output=True, text=True)
        print("Build success!")
        print("Output dir: dist_nuitka/")
        print("Executable: dist_nuitka/AutoHomework.exe")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        print("stderr:", e.stderr)
        return False

if __name__ == "__main__":    
    build_with_nuitka()
