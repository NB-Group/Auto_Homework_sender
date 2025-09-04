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
        "--standalone",  # standalone模式
        "--windows-console-mode=disable",  # 禁用控制台窗口
        "--windows-icon-from-ico=icon.ico",  # 添加图标
        "--include-data-dir=static=static",  # 包含static目录
        "--output-dir=dist",  # 输出目录
        "--output-filename=AutoHomework.exe",  # 输出文件名
        "--assume-yes-for-downloads",  # 自动下载依赖
        "--plugin-enable=tk-inter",  # 启用tkinter插件
        "--include-module=webview.platforms.edgechromium",  # 指定webview平台
        "--include-module=schedule",
        "--include-module=requests",
        "--include-module=pptx",
        "--include-module=json",
        "--include-module=threading",
        "--include-module=pathlib",
        "--include-module=winreg",  # 用于开机启动管理
        "--include-module=logging",
        "--include-module=argparse",
        "--include-data-file=service_mode.py=service_mode.py",  # 包含服务模式文件
        "--include-data-file=autostart_manager.py=autostart_manager.py",  # 包含开机启动管理文件
        "--include-data-file=setup_autostart.py=setup_autostart.py",  # 包含设置脚本
        "--include-data-file=setup_autostart.bat=setup_autostart.bat",  # 包含批处理文件
        "--include-data-file=AUTOSTART_README.md=AUTOSTART_README.md",  # 包含说明文档
        "main.py"
    ]
    
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
