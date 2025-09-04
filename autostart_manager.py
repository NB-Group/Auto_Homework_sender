#!/usr/bin/env python3
"""
开机启动项管理模块
负责管理Windows注册表中的开机启动项
"""

import os
import sys
import winreg
import logging
from pathlib import Path
from typing import Optional, Tuple

class AutostartManager:
    """开机启动项管理器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.last_error_code = None  # 记录最近一次失败原因，供上层展示
        self.last_error_message = None

        # 注册表路径
        self.reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

        # 应用信息
        self.app_name_ui = "AutoHomework_UI"
        self.app_name_service = "AutoHomework_Service"

        # 获取可执行文件路径
        self._get_executable_paths()

    def _get_executable_paths(self):
        """获取可执行文件路径"""
        try:
            # 打包后的 exe：直接使用当前可执行文件路径，避免名称硬编码
            if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS'):
                exe_dir = os.path.dirname(sys.executable)
                self.exe_path = sys.executable  # 实际发布名称（如 AutoHomework.exe）
                self.service_path = os.path.join(exe_dir, "service_mode.exe")
            else:
                # 开发环境 - 使用pythonw.exe避免显示CMD窗口
                script_dir = os.path.dirname(os.path.abspath(__file__))
                self.exe_path = os.path.join(script_dir, "main.py")
                self.service_path = os.path.join(script_dir, "service_mode.py")

                # 获取pythonw.exe路径（无窗口版本的Python解释器）
                python_exe = sys.executable
                pythonw_exe = python_exe.replace('python.exe', 'pythonw.exe')

                # 验证pythonw.exe是否存在，如果不存在则回退到python.exe
                if os.path.exists(pythonw_exe):
                    python_exe = pythonw_exe
                    self.logger.info("使用pythonw.exe避免显示CMD窗口")
                else:
                    self.logger.warning("pythonw.exe不存在，使用python.exe（可能会显示CMD窗口）")

                # 构建启动命令
                self.exe_path = f'"{python_exe}" "{self.exe_path}" --ui'
                self.service_path = f'"{python_exe}" "{self.service_path}" --service'

            self.logger.info(f"UI启动路径: {self.exe_path}")
            self.logger.info(f"服务启动路径: {self.service_path}")

        except Exception as e:
            self.logger.error(f"获取可执行文件路径失败: {e}")
            raise

    def _open_registry_key(self, write=False) -> winreg.HKEYType:
        """打开注册表键"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.reg_path,
                0,
                winreg.KEY_READ | (winreg.KEY_WRITE if write else 0)
            )
            return key
        except PermissionError as e:
            self.last_error_code = 'PERMISSION_DENIED'
            self.last_error_message = '没有权限写入注册表（需要以管理员权限运行）'
            self.logger.error(f"打开注册表键失败(权限): {e}")
            raise
        except Exception as e:
            self.last_error_code = 'OPEN_KEY_FAILED'
            self.last_error_message = str(e)
            self.logger.error(f"打开注册表键失败: {e}")
            raise

    def _set_autostart_entry(self, name: str, command: str) -> bool:
        """设置开机启动项"""
        try:
            with self._open_registry_key(write=True) as key:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
                self.logger.info(f"设置开机启动项成功: {name} -> {command}")
                return True
        except PermissionError as e:
            self.last_error_code = 'PERMISSION_DENIED'
            self.last_error_message = '没有权限写入注册表（需要以管理员权限运行）'
            self.logger.error(f"设置开机启动项失败(权限): {e}")
            return False
        except Exception as e:
            self.last_error_code = 'SET_VALUE_FAILED'
            self.last_error_message = str(e)
            self.logger.error(f"设置开机启动项失败: {e}")
            return False

    def _remove_autostart_entry(self, name: str) -> bool:
        """删除开机启动项"""
        try:
            with self._open_registry_key(write=True) as key:
                winreg.DeleteValue(key, name)
                self.logger.info(f"删除开机启动项成功: {name}")
                return True
        except FileNotFoundError:
            self.logger.info(f"开机启动项不存在: {name}")
            return True
        except PermissionError as e:
            self.last_error_code = 'PERMISSION_DENIED'
            self.last_error_message = '没有权限写入注册表（需要以管理员权限运行）'
            self.logger.error(f"删除开机启动项失败(权限): {e}")
            return False
        except Exception as e:
            self.last_error_code = 'DELETE_VALUE_FAILED'
            self.last_error_message = str(e)
            self.logger.error(f"删除开机启动项失败: {e}")
            return False

    def _get_autostart_entry(self, name: str) -> Optional[str]:
        """获取开机启动项"""
        try:
            with self._open_registry_key() as key:
                value, _ = winreg.QueryValueEx(key, name)
                return value
        except FileNotFoundError:
            return None
        except Exception as e:
            self.logger.error(f"获取开机启动项失败: {e}")
            return None

    def enable_ui_autostart(self) -> bool:
        """启用UI开机启动"""
        # exe_path已经包含了必要的参数
        return self._set_autostart_entry(self.app_name_ui, self.exe_path)

    def disable_ui_autostart(self) -> bool:
        """禁用UI开机启动"""
        return self._remove_autostart_entry(self.app_name_ui)

    def enable_service_autostart(self) -> bool:
        """启用服务开机启动"""
        # service_path已经包含了必要的参数
        return self._set_autostart_entry(self.app_name_service, self.service_path)

    def disable_service_autostart(self) -> bool:
        """禁用服务开机启动"""
        return self._remove_autostart_entry(self.app_name_service)

    def is_ui_autostart_enabled(self) -> bool:
        """检查UI开机启动是否启用"""
        return self._get_autostart_entry(self.app_name_ui) is not None

    def is_service_autostart_enabled(self) -> bool:
        """检查服务开机启动是否启用"""
        return self._get_autostart_entry(self.app_name_service) is not None

    def get_autostart_status(self) -> dict:
        """获取开机启动状态"""
        return {
            "ui_autostart": self.is_ui_autostart_enabled(),
            "ui_path": self._get_autostart_entry(self.app_name_ui)
        }

    def apply_config(self, config: dict) -> dict:
        """根据配置应用开机启动设置"""
        results = {}

        # UI开机启动 - 直接显示UI，不显示启动模式提示
        ui_enabled = config.get("auto_start_ui", True)
        if ui_enabled and not self.is_ui_autostart_enabled():
            ok = self.enable_ui_autostart()
            results["ui_autostart"] = ok
            if not ok:
                results["error"] = self.last_error_message or '设置UI开机启动失败'
        elif not ui_enabled and self.is_ui_autostart_enabled():
            ok = self.disable_ui_autostart()
            results["ui_autostart"] = ok
            if not ok:
                results["error"] = self.last_error_message or '取消UI开机启动失败'
        else:
            results["ui_autostart"] = True  # 已经是期望状态

        return results

def main():
    """主函数，用于测试"""
    logging.basicConfig(level=logging.INFO)

    manager = AutostartManager()

    # 打印当前状态
    status = manager.get_autostart_status()
    print("当前开机启动状态:")
    for key, value in status.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    main()


