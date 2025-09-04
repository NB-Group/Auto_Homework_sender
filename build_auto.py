#!/usr/bin/env python3
"""
一键打包脚本
自动安装依赖、构建可执行文件并创建安装包
"""

import os
import sys
import subprocess
import shutil
import time
from pathlib import Path

class AutoBuilder:
    """自动构建器"""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.dist_dir = self.project_root / "dist"
        self.build_dir = self.project_root / "build"

    def run_command(self, cmd, description=""):
        """运行命令"""
        print(f"\n{'='*50}")
        if description:
            print(f"执行: {description}")
        print(f"命令: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        print('='*50)

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            if result.stdout:
                print(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ 执行失败: {e}")
            if e.stdout:
                print(f"标准输出: {e.stdout}")
            if e.stderr:
                print(f"错误输出: {e.stderr}")
            return False

    def install_dependencies(self):
        """安装依赖"""
        print("\n📦 安装Python依赖...")
        return self.run_command([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], "安装项目依赖")

    def clean_build_dirs(self):
        """清理构建目录"""
        print("\n🧹 清理构建目录...")
        dirs_to_clean = [self.dist_dir, self.build_dir]
        success = True

        for dir_path in dirs_to_clean:
            if dir_path.exists():
                try:
                    shutil.rmtree(dir_path)
                    print(f"已删除: {dir_path}")
                except Exception as e:
                    print(f"删除失败 {dir_path}: {e}")
                    success = False

        return success

    def build_with_nuitka(self):
        """使用Nuitka构建"""
        print("\n🔨 使用Nuitka构建可执行文件...")

        cmd = [
            sys.executable, "-m", "nuitka",
            "--standalone",
            "--windows-console-mode=disable",
            "--windows-icon-from-ico=icon.ico",
            "--include-data-dir=static=static",
            "--output-dir=str(dist)",
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
            "--include-module=pystray",
            "--include-module=PIL",
            "--include-module=socket",
            "--include-module=tempfile",
            "--windows-disable-console",  # 确保无控制台
            "main.py"
        ]

        return self.run_command(cmd, "Nuitka构建")

    def create_installer(self):
        """创建安装包"""
        print("\n📦 创建安装包...")

        installer_script = self.project_root / "installer_setup.iss"
        if not installer_script.exists():
            print("❌ 找不到Inno Setup脚本文件")
            return False

        # 使用Inno Setup创建安装包
        cmd = [
            "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe",
            str(installer_script)
        ]

        return self.run_command(cmd, "创建安装包")

    def optimize_build(self):
        """优化构建结果"""
        print("\n⚡ 优化构建结果...")

        exe_path = self.dist_dir / "main.dist" / "AutoHomework.exe"
        if exe_path.exists():
            # 可以在这里添加更多的优化步骤
            print(f"✅ 可执行文件已生成: {exe_path}")
            print(f"文件大小: {exe_path.stat().st_size / (1024*1024):.2f} MB")
            return True
        else:
            print("❌ 找不到生成的可执行文件")
            return False

    def build(self):
        """执行完整构建流程"""
        print("🚀 开始一键打包 Auto Homework")
        print(f"项目目录: {self.project_root}")

        steps = [
            ("清理构建目录", self.clean_build_dirs),
            ("安装依赖", self.install_dependencies),
            ("Nuitka构建", self.build_with_nuitka),
            ("优化构建", self.optimize_build),
            ("创建安装包", self.create_installer),
        ]

        start_time = time.time()

        for step_name, step_func in steps:
            print(f"\n🔄 {step_name}...")
            if not step_func():
                print(f"❌ {step_name}失败，构建终止")
                return False

        end_time = time.time()
        duration = end_time - start_time

        print("\n🎉 构建完成!")
        print(f"总耗时: {duration:.2f}秒")
        print(f"输出目录: {self.dist_dir}")

        return True

def main():
    """主函数"""
    builder = AutoBuilder()

    try:
        success = builder.build()
        if success:
            print("\n✅ 一键打包成功!")
            print("您可以在 dist 目录中找到生成的文件")
        else:
            print("\n❌ 打包失败!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断构建")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 构建过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
