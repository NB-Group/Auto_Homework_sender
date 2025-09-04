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
    """使用Nuitka构建可执行文件 - 正式版本"""
    
    # Nuitka命令参数 - 禁用控制台的正式版本
    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--windows-console-mode=disable",
        "--windows-icon-from-ico=icon.ico",
        "--output-dir=dist",
        "--output-filename=AutoHomework.exe",
        "--assume-yes-for-downloads",
        "--plugin-enable=tk-inter",
        "--include-module=webview.platforms.edgechromium",
        "--include-module=schedule",
        "--include-module=requests",
        "--include-module=pptx",
        "--include-module=json",
        "--include-module=threading",
        "--include-module=pathlib",
        "--include-module=winreg",
        "--include-module=logging",
        "--include-module=argparse",
    ]

    # 条件包含静态资源与脚本文件，避免CI缺失文件导致失败
    if os.path.isdir("static"):
        nuitka_cmd += ["--include-data-dir=static=static"]
    for f in [
        "service_mode.py",
        "autostart_manager.py",
        "setup_autostart.py",
        "setup_autostart.bat",
        "AUTOSTART_README.md",
    ]:
        if os.path.exists(f):
            nuitka_cmd += [f"--include-data-file={f}={f}"]

    nuitka_cmd += ["main.py"]
    
    print("Start building with Nuitka (release mode)...")
    print("Command:", " ".join(nuitka_cmd))
    
    try:
        result = subprocess.run(nuitka_cmd, check=True, capture_output=True, text=True)
        print("Build success!")
        print("Output dir: dist/main.dist/")
        print("Executable: dist/main.dist/AutoHomework.exe")
        print("\nRelease build created (console disabled)")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        print("stderr:", e.stderr)
        return False

if __name__ == "__main__":    
    build_with_nuitka()
