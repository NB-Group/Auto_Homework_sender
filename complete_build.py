#!/usr/bin/env python3
"""
完整构建和打包脚本
构建可执行文件并生成安装包
"""

import os
import sys
import subprocess
import shutil
import time
from pathlib import Path

class CompleteBuilder:
    """完整构建器"""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.dist_dir = self.project_root / "dist_nuitka"
        self.build_dir = self.project_root / "build"
        self.installer_dir = self.project_root / "installer"

    def run_command(self, cmd, description="", check=True):
        """运行命令"""
        print(f"\n{'='*60}")
        if description:
            print(f"📋 {description}")
        print(f"命令: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        print('='*60)

        try:
            result = subprocess.run(
                cmd,
                check=check,
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

    def clean_build_dirs(self):
        """清理构建目录"""
        print("\n🧹 清理构建目录...")
        dirs_to_clean = [self.dist_dir, self.build_dir]
        success = True

        for dir_path in dirs_to_clean:
            if dir_path.exists():
                try:
                    shutil.rmtree(dir_path)
                    print(f"✅ 已删除: {dir_path}")
                except Exception as e:
                    print(f"⚠️  删除失败 {dir_path}: {e}")
                    success = False

        return success

    def install_dependencies(self):
        """安装依赖"""
        print("\n📦 安装Python依赖...")
        return self.run_command([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], "安装项目依赖")

    def build_with_nuitka(self):
        """使用Nuitka构建"""
        print("\n🔨 使用Nuitka构建可执行文件...")

        cache_dir = os.environ.get("CACHE_DIR", os.path.join(os.getenv("TEMP", "."), "nuitka-cache"))

        cmd = [
            sys.executable, "-m", "nuitka",
            "--onefile",
            f"--onefile-tempdir-spec={cache_dir}",
            "--standalone",
            "--assume-yes-for-downloads",
            "--disable-console",
            "--enable-plugin=tk-inter",
            "--include-data-dir=static=static",
            "--include-data-files=icon.ico=icon.ico",
            "--windows-icon-from-ico=icon.ico",
            "--output-dir=dist_nuitka",
            "main.py"
        ]

        success = self.run_command(cmd, "Nuitka构建", check=False)

        # 检查构建结果
        exe_path = self.dist_dir / "main.exe"
        if exe_path.exists():
            file_size = exe_path.stat().st_size / (1024 * 1024)
            print("✅ 构建成功!")
            print(f"📁 可执行文件: {exe_path}")
            print(f"📊 文件大小: {file_size:.2f} MB")
            return True
        else:
            print("❌ 构建失败：找不到生成的可执行文件")
            return False

    def create_installer(self):
        """创建安装包"""
        print("\n📦 创建安装包...")

        # 检查Inno Setup
        inno_setup_paths = [
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe"
        ]

        iscc_path = None
        for path in inno_setup_paths:
            if os.path.exists(path):
                iscc_path = path
                break

        if not iscc_path:
            print("❌ 找不到Inno Setup，请安装Inno Setup 6")
            print("下载地址: https://jrsoftware.org/isdl.php")
            return False

        # 检查构建文件是否存在
        exe_dir = self.dist_dir / "main.dist"
        if not exe_dir.exists():
            print(f"❌ 找不到构建文件目录: {exe_dir}")
            return False

        # 运行Inno Setup
        iss_file = self.project_root / "installer_setup.iss"
        if not iss_file.exists():
            print(f"❌ 找不到ISS文件: {iss_file}")
            return False

        cmd = [iscc_path, str(iss_file)]
        success = self.run_command(cmd, "创建安装包")

        if success:
            # 检查安装包是否生成
            installer_pattern = "AutoHomework_Setup_v*.exe"
            installer_files = list(self.installer_dir.glob(installer_pattern))

            if installer_files:
                installer_file = installer_files[0]
                file_size = installer_file.stat().st_size / (1024 * 1024)
                print("✅ 安装包创建成功!")
                print(f"📁 安装包文件: {installer_file}")
                print(f"📊 安装包大小: {file_size:.2f} MB")
                return True
            else:
                print("❌ 找不到生成的安装包文件")
                return False

        return success

    def build(self):
        """执行完整构建流程"""
        print("🚀 开始完整构建 Auto Homework")
        print(f"项目目录: {self.project_root}")
        print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        steps = [
            ("清理构建目录", self.clean_build_dirs),
            ("安装依赖", self.install_dependencies),
            ("Nuitka构建", self.build_with_nuitka),
            ("创建安装包", self.create_installer),
        ]

        start_time = time.time()
        completed_steps = []

        for step_name, step_func in steps:
            print(f"\n🔄 {step_name}...")
            if step_func():
                completed_steps.append(step_name)
                print(f"✅ {step_name} 完成")
            else:
                print(f"❌ {step_name} 失败")
                break

        end_time = time.time()
        duration = end_time - start_time

        print("
" + "="*60)
        print("📊 构建报告:"        print(f"⏱️  总耗时: {duration:.2f}秒")
        print(f"✅ 完成步骤: {len(completed_steps)}/{len(steps)}")

        for i, step in enumerate(steps, 1):
            status = "✅" if step[0] in completed_steps else "❌"
            print(f"   {i}. {status} {step[0]}")

        if len(completed_steps) == len(steps):
            print("
🎉 构建完全成功!"            print(f"📁 输出目录: {self.dist_dir}")
            print(f"📦 安装包目录: {self.installer_dir}")
            return True
        else:
            print("
❌ 构建未完成"            return False

def main():
    """主函数"""
    builder = CompleteBuilder()

    try:
        success = builder.build()
        if success:
            print("\n🎊 恭喜！Auto Homework 完整构建成功！")
            print("你现在可以:")
            print("1. 运行 dist/main.dist/AutoHomework.exe 测试应用")
            print("2. 运行 installer/AutoHomework_Setup_v1.0.0.exe 安装应用")
        else:
            print("\n❌ 构建失败，请检查上述错误信息")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断构建")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 构建过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
