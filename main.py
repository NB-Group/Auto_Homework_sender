import os
import sys
import threading
import time
import argparse
from datetime import datetime

import schedule
import webview
import traceback
import json

from homework_api import HomeworkAPI
from autostart_manager import AutostartManager
from flask import Flask, request as flask_request, jsonify, make_response

# 单实例相关导入
try:
    import socket
    import tempfile
    SINGLE_INSTANCE_AVAILABLE = True
except ImportError:
    SINGLE_INSTANCE_AVAILABLE = False


def _resolve_index_html_path() -> str:
    """获取前端入口文件绝对路径，兼容打包与开发环境。"""
    # 优先：打包后的可执行文件所在目录（Nuitka / PyInstaller 均可用）
    try:
        if getattr(sys, 'frozen', False) or hasattr(sys, "_MEIPASS"):
            exe_dir = os.path.dirname(sys.executable)
            index_path = os.path.join(exe_dir, "static", "index.html")
            if os.path.exists(index_path):
                return index_path
    except Exception:
        pass

    # 退回到源码所在目录
    script_dir = os.path.abspath(os.path.dirname(__file__))
    index_path = os.path.join(script_dir, "static", "index.html")
    if os.path.exists(index_path):
        return index_path

    # 最后尝试当前工作目录
    cwd_index = os.path.join(os.path.abspath("."), "static", "index.html")
    return cwd_index


# 全局引用当前UI窗口（供 API 方法调用）
_MAIN_WINDOW = None
_REST_SERVER = None
REST_FIXED_PORT = 58701  # 固定REST端口，避免随机端口导致发现失败
APP_VERSION = "1.0.0"


class ScheduleManager:
    """负责根据配置安排与运行每日自动发送任务。"""

    def __init__(self, api: HomeworkAPI):
        self.api = api
        self._thread = None
        self._stop_event = threading.Event()
        self._scheduled_time_str = None

    def _loop(self):
        while not self._stop_event.is_set():
            try:
                schedule.run_pending()
            except Exception:
                # 避免调度循环因异常中断
                pass
            time.sleep(1)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="SchedulerLoop", daemon=True)
        self._thread.start()

    def shutdown(self):
        self._stop_event.set()
        try:
            if self._thread:
                self._thread.join(timeout=2)
        except Exception:
            pass

    def apply_config(self, config: dict):
        """根据配置重建调度任务。"""
        schedule.clear()
        self._scheduled_time_str = None

        enabled = bool(config.get("auto_send_enabled"))

        if not enabled:
            return

        # 获取工作日和周五的时间设置
        weekday_time = str(config.get("weekday_send_time", config.get("auto_send_time", "09:00")))
        friday_time = str(config.get("friday_send_time", config.get("auto_send_time", "09:00")))

        def _task():
            try:
                result = self.api.auto_send_homework()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"[Auto Send] {timestamp} -> {result}")

                # 发送完成后显示通知
                self._show_send_notification(result, timestamp)

            except Exception as exc:
                print(f"[Auto Send] 任务异常: {exc}")
                # 异常时也显示通知
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self._show_send_notification({"success": False, "error": str(exc)}, timestamp)

        try:
            # 获取当前日期是星期几 (0=周一, 1=周二, ..., 4=周五, 5=周六, 6=周日)
            today = datetime.now()
            weekday = today.weekday()

            # 根据星期几选择不同的发送时间
            if weekday == 4:  # 周五
                time_str = friday_time
            else:  # 周一到周四
                time_str = weekday_time

            # 安排明天的任务
            schedule.every().day.at(time_str).do(_task)
            self._scheduled_time_str = time_str
            self.start()

            print(f"[Scheduler] 已安排任务 - 周{weekday+1}: {time_str}")

        except Exception as exc:
            print(f"[Scheduler] 无法安排每日任务: {exc}")

    def _show_send_notification(self, result: dict, timestamp: str):
        """显示发送完成通知"""
        try:
            # 构建通知消息
            if result.get("success"):
                title = "作业发送成功"
                message = f"作业已于 {timestamp} 成功发送到钉钉"
            else:
                title = "作业发送失败"
                error_msg = result.get("error", "未知错误")
                message = f"作业发送失败: {error_msg}"

            # 尝试显示系统通知
            try:
                import plyer
                plyer.notification.notify(
                    title=title,
                    message=message,
                    app_name="Auto Homework",
                    timeout=10
                )
            except ImportError:
                # 如果没有plyer，使用webview的JavaScript通知
                try:
                    if _MAIN_WINDOW:
                        notification_js = f"""
                        if ('Notification' in window) {{
                            if (Notification.permission === 'granted') {{
                                new Notification('{title}', {{
                                    body: '{message}',
                                    icon: 'icon.ico'
                                }});
                            }} else if (Notification.permission !== 'denied') {{
                                Notification.requestPermission().then(function(permission) {{
                                    if (permission === 'granted') {{
                                        new Notification('{title}', {{
                                            body: '{message}',
                                            icon: 'icon.ico'
                                        }});
                                    }}
                                }});
                            }}
                        }}
                        """
                        _MAIN_WINDOW.evaluate_js(notification_js)
                except Exception:
                    pass

        except Exception as e:
            print(f"[Notification] 显示通知失败: {e}")

    def get_status(self) -> dict:
        """提供完整状态。注意：若外部担心阻塞，可改用 get_status_fast。"""
        # 为避免潜在阻塞，对 next_run 与磁盘 IO 做保护
        try:
            next_run = schedule.next_run()
        except Exception:
            next_run = None

        try:
            # 直接读取内存配置，避免不必要的磁盘 IO
            config = getattr(self.api, "config", None) or self.api.get_config()
        except Exception:
            config = {}

        weekday = datetime.now().weekday()
        if weekday == 4:  # 周五
            current_time = config.get("friday_send_time", config.get("auto_send_time", "09:00"))
        else:  # 周一到周四
            current_time = config.get("weekday_send_time", config.get("auto_send_time", "09:00"))

        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]

        return {
            "auto_send_enabled": bool(config.get("auto_send_enabled")),
            "scheduler_running": bool(self._thread and self._thread.is_alive() and len(schedule.jobs) > 0),
            "scheduled_time": self._scheduled_time_str,
            "current_time": current_time,
            "current_weekday": f"周{weekday_names[weekday]}",
            "weekday_send_time": config.get("weekday_send_time", config.get("auto_send_time", "09:00")),
            "friday_send_time": config.get("friday_send_time", config.get("auto_send_time", "09:00")),
            "next_run": str(next_run) if next_run else "None",
        }

    def get_status_fast(self) -> dict:
        """极简状态，避免任何可能的阻塞调用。"""
        config = getattr(self.api, "config", {})
        weekday = datetime.now().weekday()
        if weekday == 4:
            current_time = config.get("friday_send_time", config.get("auto_send_time", "09:00"))
        else:
            current_time = config.get("weekday_send_time", config.get("auto_send_time", "09:00"))

        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        return {
            "auto_send_enabled": bool(config.get("auto_send_enabled")),
            "scheduler_running": bool(self._thread and self._thread.is_alive() and len(schedule.jobs) > 0),
            "scheduled_time": self._scheduled_time_str,
            "current_time": current_time,
            "current_weekday": f"周{weekday_names[weekday]}",
            "weekday_send_time": config.get("weekday_send_time", config.get("auto_send_time", "09:00")),
            "friday_send_time": config.get("friday_send_time", config.get("auto_send_time", "09:00")),
            "next_run": "Unknown",
        }


class SingleInstanceManager:
    """
    通过在临时目录创建锁文件和TCP套接字来管理应用的单实例。
    - 第一个实例（服务器）：创建锁文件，监听TCP端口。锁文件包含PID和端口号。
    - 后续实例（客户端）：检查锁文件，如果存在且PID有效，则连接到指定端口发送激活命令，然后退出。
    """
    def __init__(self, app_name="AutoHomework"):
        self.app_name = app_name
        self.lock_file_path = os.path.join(tempfile.gettempdir(), f"{self.app_name}.lock")
        self.server_socket = None
        self._is_server = False

    def _get_lock_info(self):
        """从锁文件读取PID和端口号。如果文件无效或进程不存在，则删除锁文件。"""
        if not os.path.exists(self.lock_file_path):
            return None, None

        try:
            with open(self.lock_file_path, 'r') as f:
                pid_str, port_str = f.read().strip().split(':')
                pid, port = int(pid_str), int(port_str)

            # 检查PID是否存在
            import psutil
            if psutil.pid_exists(pid):
                return pid, port
            else:
                # 进程不存在，锁文件已失效
                self._release_lock()
                return None, None
        except (ValueError, FileNotFoundError, ImportError):
            self._release_lock()
            return None, None
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # 进程存在但无法访问，保守地认为实例仍在运行
            return pid, port

    def _create_lock(self, port):
        """创建锁文件，写入当前进程PID和监听的端口号。"""
        with open(self.lock_file_path, 'w') as f:
            f.write(f"{os.getpid()}:{port}")
        self._is_server = True

    def _release_lock(self):
        """如果当前进程是服务器，则删除锁文件。"""
        if self._is_server:
            try:
                if os.path.exists(self.lock_file_path):
                    os.remove(self.lock_file_path)
            except OSError:
                pass

    def become_server(self):
        """
        尝试成为服务器实例。
        如果成功，启动监听线程并返回True。
        如果已有实例在运行，返回False。
        """
        existing_pid, _ = self._get_lock_info()
        if existing_pid:
            return False  # 已有实例在运行

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind(('localhost', 0))  # 绑定到随机可用端口
            self.server_socket.listen(1)
            _, port = self.server_socket.getsockname()

            self._create_lock(port)

            # 启动监听线程
            listener_thread = threading.Thread(target=self._listen_for_commands, daemon=True)
            listener_thread.start()
            print(f"[Instance] 已成为主实例，PID: {os.getpid()}, Port: {port}")
            return True
        except (socket.error, OSError):
            self.cleanup()
            return False

    def activate_existing_instance(self):
        """激活已存在的实例。
        首先尝试使用 Windows API 直接激活窗口（更可靠、无须服务端线程）。
        如果失败，再回退到socket命令。
        """
        # Windows 直接激活（首选）
        try:
            if sys.platform.startswith("win"):
                import win32gui
                import win32con
                import win32api
                hwnd = win32gui.FindWindow(None, "Auto Homework")
                if hwnd:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    win32gui.BringWindowToTop(hwnd)
                    print("[Instance] 已通过Win32 API激活窗口")
                    return True
        except Exception as e:
            print(f"[Instance] Win32 激活失败: {e}")

        # 回退到socket
        _, port = self._get_lock_info()
        if not port:
            return False

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.settimeout(1.0)
                client_socket.connect(('localhost', port))
                client_socket.sendall(b"SHOW_WINDOW")
            print(f"[Instance] 已发送激活命令到端口 {port}")
            return True
        except (socket.error, socket.timeout):
            print("[Instance] 通过socket激活失败")
            return False

    def _listen_for_commands(self):
        """监听来自其他实例的命令。"""
        while self._is_server:
            try:
                client, _ = self.server_socket.accept()
                with client:
                    data = client.recv(1024)
                    if data == b"SHOW_WINDOW":
                        print("[Instance] 收到激活命令")
                        self._show_main_window_thread_safe()
            except (socket.error, OSError):
                break  # 服务器套接字已关闭

    def _show_main_window_thread_safe(self):
        """线程安全地显示主窗口。优先使用Win32提升可靠性，回退JS。"""
        # 1) Windows 原生方式（最可靠，不依赖JS环境）
        if sys.platform.startswith("win"):
            try:
                import win32gui
                import win32con
                hwnd = win32gui.FindWindow(None, "Auto Homework")
                if hwnd:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.BringWindowToTop(hwnd)
                    try:
                        win32gui.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
                    print("[Instance] 已通过Win32 API激活窗口(服务端)")
                    return
            except Exception as e:
                print(f"[Instance] 服务端Win32激活失败: {e}")

        # 2) 回退：通过JS触发后端API在GUI线程中显示窗口
        if _MAIN_WINDOW:
            try:
                print("[Instance] 正在通过JS API调用show_window() 以回退激活...")
                _MAIN_WINDOW.evaluate_js('pywebview.api.show_window()')
            except Exception as e:
                print(f"[Instance] evaluate_js 回退激活失败: {e}")

    def cleanup(self):
        """清理资源。"""
        self._release_lock()
        if self.server_socket:
            try:
                self.server_socket.close()
            except socket.error:
                pass
        self._is_server = False





class ApiBridge:
    """暴露给前端的API桥接层，封装 HomeworkAPI 并管理调度。"""

    def __init__(self, api: HomeworkAPI, scheduler: ScheduleManager):
        self._api = api
        self._scheduler = scheduler
        self._autostart_manager = AutostartManager()

    # 窗口控制方法（供前端调用）
    def minimize(self):
        try:
            global _MAIN_WINDOW
            # Windows优先使用Win32 API，提升兼容性
            if sys.platform.startswith("win"):
                try:
                    import win32gui
                    import win32con
                    hwnd = win32gui.FindWindow(None, "Auto Homework")
                    if hwnd:
                        # 尝试最小化到任务栏
                        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                        return {"success": True}
                except Exception:
                    pass

            if _MAIN_WINDOW:
                try:
                    _MAIN_WINDOW.minimize()
                except Exception:
                    # 回退：隐藏窗口
                    try:
                        _MAIN_WINDOW.hide()
                    except Exception:
                        return {"success": False, "error": "无法最小化或隐藏窗口"}
                return {"success": True}
            return {"success": False, "error": "窗口不可用"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close(self):
        try:
            global _MAIN_WINDOW
            # Windows优先使用Win32 API隐藏窗口，避免边框/无边框兼容问题
            if sys.platform.startswith("win"):
                try:
                    import win32gui
                    import win32con
                    hwnd = win32gui.FindWindow(None, "Auto Homework")
                    if hwnd:
                        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                        return {"success": True}
                except Exception:
                    pass

            if _MAIN_WINDOW:
                try:
                    _MAIN_WINDOW.hide()
                    return {"success": True}
                except Exception as e:
                    # 回退：最小化
                    try:
                        _MAIN_WINDOW.minimize()
                        return {"success": True}
                    except Exception:
                            return {"success": False, "error": f"隐藏/最小化失败: {e}"}
            return {"success": False, "error": "窗口不可用"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # show_window 实现在类下方更完整的版本，移除此处的重复定义

    def open_devtools(self):
        """打开/切换 DevTools（需要 webview.start(debug=True)）"""
        return {"success": False, "error": "DevTools 已禁用"}

    # 基础能力
    def select_ppt_file(self):
        return self._api.select_ppt_file()

    def preview_homework(self, file_path: str):
        return self._api.preview_homework(file_path)

    def send_homework(self, file_path: str):
        return self._api.send_homework(file_path)

    def get_config(self):
        try:
            cfg = self._api.get_config()
            try:
                print("[ApiBridge] get_config called, keys:", list(cfg.keys()))
                sys.stdout.flush()
            except Exception:
                pass
            return cfg
        except Exception as e:
            try:
                print("[ApiBridge] get_config error:", e)
                sys.stdout.flush()
            except Exception:
                pass
            return {"success": False, "error": str(e)}

    def save_config(self, config: dict):
        result = self._api.save_config(config)
        if not result.get("success", False):
            return result

        # 配置保存后，立即同步调度器
        try:
            self._scheduler.apply_config(self._api.get_config())
        except Exception as exc:
            return {"success": False, "error": f"配置已保存，但调度器更新失败: {exc}"}

        # 应用开机启动配置
        try:
            autostart_result = self._autostart_manager.apply_config(config)
            if not all(autostart_result.values()):
                return {"success": False, "error": f"配置已保存，但开机启动设置失败: {autostart_result}"}
        except Exception as exc:
            return {"success": False, "error": f"配置已保存，但开机启动设置失败: {exc}"}

        return result

    # 调度状态
    def get_scheduler_status(self):
        # 对外提供快速状态，避免阻塞；如需完整信息可在前端改调 get_scheduler_status_full
        try:
            return self._scheduler.get_status_fast()
        except Exception as e:
            try:
                print("[ApiBridge] get_scheduler_status error:", e)
            except Exception:
                pass
            return {"success": False, "error": str(e)}

    def get_scheduler_status_full(self):
        try:
            return self._scheduler.get_status()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_rest_base(self):
        """提供本地REST服务基地址，供前端发现。"""
        try:
            global _REST_SERVER
            base = _REST_SERVER.base_url if _REST_SERVER else ''
            return {"success": True, "base": base}
        except Exception as e:
            return {"success": False, "error": str(e)}


class RestServer:
    """基于 Flask 的本地 REST 服务。"""

    def __init__(self, api: HomeworkAPI, scheduler: ScheduleManager, autostart: AutostartManager):
        self.api = api
        self.scheduler = scheduler
        self.autostart = autostart
        self.port = None
        self._thread = None
        app = Flask(__name__)

        def cors(resp):
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept, X-Requested-With'
            return resp

        @app.after_request
        def add_cors_headers(resp):
            # 全局添加CORS响应头，保证预检/异常响应也包含CORS
            resp.headers.setdefault('Access-Control-Allow-Origin', '*')
            resp.headers.setdefault('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            resp.headers.setdefault('Access-Control-Allow-Headers', 'Content-Type, Accept, X-Requested-With')
            return resp

        @app.route('/api/ping', methods=['GET', 'OPTIONS'])
        def ping():
            return cors(make_response(jsonify({"success": True, "pong": True}), 200))

        @app.route('/api/update/check', methods=['GET'])
        def update_check():
            """从 GitHub Releases 检查最新版本。返回 tag、下载链接和是否有更新。"""
            import re, json as _json
            owner_repo = 'NB-Group/Auto_Homework_sender'
            try:
                import requests as _rq
                r = _rq.get(f'https://api.github.com/repos/{owner_repo}/releases/latest', timeout=8)
                info = r.json()
                latest_tag = info.get('tag_name') or ''
                assets = info.get('assets') or []
                asset_url = ''
                for a in assets:
                    name = a.get('name','')
                    if name.endswith('.exe'):
                        asset_url = a.get('browser_download_url')
                        break
                mirrors = []
                if asset_url:
                    try:
                        # 常用 GitHub 加速镜像前缀（多备选）
                        mirrors = [
                            'https://ghproxy.com/',
                            'https://mirror.ghproxy.com/'
                        ]
                        mirrors = [m + asset_url for m in mirrors]
                    except Exception:
                        mirrors = []
                return cors(make_response(jsonify({
                    'success': True,
                    'latest': latest_tag,
                    'download': asset_url,
                    'mirrors': mirrors
                }), 200))
            except Exception as e:
                return cors(make_response(jsonify({'success': False, 'error': str(e)}), 200))

        @app.route('/api/config', methods=['GET'])
        def get_config():
            return cors(make_response(jsonify(self.api.get_config()), 200))

        @app.route('/api/config', methods=['POST', 'OPTIONS'])
        def save_config():
            if flask_request.method == 'OPTIONS':
                return cors(make_response('', 200))
            data = flask_request.get_json(silent=True) or {}
            # 支持直接贴入 webhook URL，解析出 access_token
            try:
                token = (data or {}).get('access_token', '')
                if isinstance(token, str) and 'access_token=' in token:
                    import urllib.parse as _up
                    parsed = _up.urlparse(token)
                    qs = _up.parse_qs(parsed.query)
                    at = (qs.get('access_token') or [''])[0]
                    if at:
                        data['access_token'] = at
            except Exception:
                pass
            result = self.api.save_config(data)
            try:
                self.scheduler.apply_config(self.api.get_config())
            except Exception:
                pass
            return cors(make_response(jsonify(result), 200))

        @app.route('/api/scheduler/status', methods=['GET'])
        def scheduler_status():
            try:
                return cors(make_response(jsonify(self.scheduler.get_status_fast()), 200))
            except Exception as e:
                return cors(make_response(jsonify({"success": False, "error": str(e)}), 200))

        @app.route('/api/select_ppt_file', methods=['POST', 'OPTIONS'])
        def select_ppt_file():
            if flask_request.method == 'OPTIONS':
                return cors(make_response('', 200))
            return cors(make_response(jsonify(self.api.select_ppt_file()), 200))

        @app.route('/api/preview_homework', methods=['POST', 'OPTIONS'])
        def preview_homework():
            if flask_request.method == 'OPTIONS':
                return cors(make_response('', 200))
            data = flask_request.get_json(silent=True) or {}
            file_path = (data or {}).get('file_path') or self.api.get_config().get('ppt_file_path')
            if not file_path:
                return cors(make_response(jsonify({"success": False, "error": "未提供文件路径"}), 200))
            return cors(make_response(jsonify(self.api.preview_homework(file_path)), 200))

        @app.route('/api/send_homework', methods=['POST', 'OPTIONS'])
        def send_homework():
            if flask_request.method == 'OPTIONS':
                return cors(make_response('', 200))
            data = flask_request.get_json(silent=True) or {}
            file_path = (data or {}).get('file_path') or self.api.get_config().get('ppt_file_path')
            if not file_path:
                return cors(make_response(jsonify({"success": False, "error": "未提供文件路径"}), 200))
            return cors(make_response(jsonify(self.api.send_homework(file_path)), 200))

        @app.route('/api/send_content', methods=['POST', 'OPTIONS'])
        def send_content():
            if flask_request.method == 'OPTIONS':
                return cors(make_response('', 200))
            data = flask_request.get_json(silent=True) or {}
            content = (data or {}).get('content')
            if not content:
                return cors(make_response(jsonify({"success": False, "error": "未提供发送内容"}), 200))
            # 直接发送内容到钉钉
            result = self.api.send_to_dingtalk(content)
            return cors(make_response(jsonify(result), 200))

        @app.route('/api/window/minimize', methods=['POST', 'OPTIONS'])
        def window_minimize():
            if flask_request.method == 'OPTIONS':
                return cors(make_response('', 200))
            try:
                global _MAIN_WINDOW
                if _MAIN_WINDOW:
                    try:
                        _MAIN_WINDOW.minimize()
                    except Exception:
                        _MAIN_WINDOW.hide()
                    return cors(make_response(jsonify({"success": True}), 200))
                return cors(make_response(jsonify({"success": False, "error": "窗口不可用"}), 200))
            except Exception as e:
                return cors(make_response(jsonify({"success": False, "error": str(e)}), 200))

        @app.route('/api/window/close', methods=['POST', 'OPTIONS'])
        def window_close():
            if flask_request.method == 'OPTIONS':
                return cors(make_response('', 200))
            try:
                global _MAIN_WINDOW
                if _MAIN_WINDOW:
                    _MAIN_WINDOW.hide()
                    return cors(make_response(jsonify({"success": True}), 200))
                return cors(make_response(jsonify({"success": False, "error": "窗口不可用"}), 200))
            except Exception as e:
                return cors(make_response(jsonify({"success": False, "error": str(e)}), 200))

        @app.route('/api/devtools/toggle', methods=['POST', 'OPTIONS'])
        def devtools_toggle():
            if flask_request.method == 'OPTIONS':
                return cors(make_response('', 200))
            # DevTools 已禁用
            return cors(make_response(jsonify({"success": False, "error": "DevTools 已禁用"}), 200))

        @app.route('/api/exit', methods=['POST', 'OPTIONS'])
        def exit_app():
            if flask_request.method == 'OPTIONS':
                return cors(make_response('', 200))
            try:
                self.scheduler.shutdown()
                os._exit(0)
            except Exception as e:
                return cors(make_response(jsonify({"success": False, "error": str(e)}), 200))

        @app.route('/api/autostart/status', methods=['GET'])
        def autostart_status():
            try:
                return cors(make_response(jsonify(self.autostart.get_autostart_status()), 200))
            except Exception as e:
                return cors(make_response(jsonify({"success": False, "error": str(e)}), 200))

        @app.route('/api/autostart/apply', methods=['POST', 'OPTIONS'])
        def autostart_apply():
            if flask_request.method == 'OPTIONS':
                return cors(make_response('', 200))
            cfg = flask_request.get_json(silent=True) or {}
            try:
                res = self.autostart.apply_config(cfg)
                ok = bool(res.get('ui_autostart'))
                return cors(make_response(jsonify({"success": ok, **res}), 200))
            except Exception as e:
                return cors(make_response(jsonify({"success": False, "error": str(e)}), 200))

        self._app = app

    def start(self):
        import threading
        # 使用固定端口，避免冲突和发现失败
        self.port = REST_FIXED_PORT

        def run_app():
            try:
                self._app.run(host='127.0.0.1', port=self.port, debug=False, use_reloader=False)
            except Exception as e:
                print('[REST] server error:', e)

        self._thread = threading.Thread(target=run_app, name='RESTServer', daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}" if self.port else ''

    # 健康检查
    def ping(self):
        """用于前端快速验证桥接是否可用。"""
        try:
            return {"success": True, "pong": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # 开机启动管理
    def get_autostart_status(self):
        """获取开机启动状态"""
        return self._autostart_manager.get_autostart_status()

    def enable_ui_autostart(self):
        """启用UI开机启动"""
        try:
            result = self._autostart_manager.enable_ui_autostart()
            return {"success": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def disable_ui_autostart(self):
        """禁用UI开机启动"""
        try:
            result = self._autostart_manager.disable_ui_autostart()
            return {"success": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def enable_service_autostart(self):
        """启用服务开机启动"""
        try:
            result = self._autostart_manager.enable_service_autostart()
            return {"success": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def disable_service_autostart(self):
        """禁用服务开机启动"""
        try:
            result = self._autostart_manager.disable_service_autostart()
            return {"success": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply_autostart_config(self, config):
        """根据配置应用开机启动设置"""
        try:
            result = self._autostart_manager.apply_config(config)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def show_window(self):
        """显示/还原主窗口并尝试刷新以避免白屏"""
        try:
            global _MAIN_WINDOW
            if _MAIN_WINDOW:
                try:
                    _MAIN_WINDOW.restore()
                except Exception:
                    pass
                try:
                    _MAIN_WINDOW.show()
                except Exception:
                    pass
                # 尝试强制刷新前端，解决某些情况下的白屏
                try:
                    _MAIN_WINDOW.evaluate_js('window.location.reload()')
                except Exception:
                    pass
                return {"success": True}
            return {"success": False, "error": "窗口不可用"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def exit_app(self):
        """彻底退出应用程序"""
        try:
            # 停止调度器
            self._scheduler.shutdown()

            # 销毁窗口
            global _MAIN_WINDOW
            if _MAIN_WINDOW:
                try:
                    _MAIN_WINDOW.destroy()
                except Exception:
                    pass

            # 退出程序
            import sys
            sys.exit(0)

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


def start_ui_mode(instance_manager=None):
    """启动UI模式"""
    api = HomeworkAPI()
    scheduler = ScheduleManager(api)
    scheduler.apply_config(api.get_config())

    api_bridge = ApiBridge(api, scheduler)

    # 启动本地 REST 服务
    autostart = AutostartManager()
    global _REST_SERVER
    _REST_SERVER = RestServer(api, scheduler, autostart)
    _REST_SERVER.start()

    index_html = _resolve_index_html_path()

    # 根据屏幕分辨率动态设置高度为屏幕3/4，宽度保持不变
    dyn_height = 800
    try:
        if sys.platform.startswith("win"):
            import win32api, win32con
            screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            dyn_height = max(600, int(screen_h * 0.75))
    except Exception:
        pass

    window = webview.create_window(
        title="Auto Homework",
        url=index_html,
        js_api=api_bridge,
        width=1100,
        height=dyn_height,
        easy_drag=False,
        frameless=True,
        resizable=True,
    )

    # 保存全局窗口引用，供 ApiBridge 使用
    global _MAIN_WINDOW
    _MAIN_WINDOW = window

    # 启动单实例监听器
    # instance_manager.listen_for_commands() # 已在become_server中启动

    def _on_closed():
        # 窗口关闭时不停止调度器，让应用继续在后台运行
        # 只有在设置中点击"彻底退出"才会停止调度器
        pass

    def _on_closing():
        # 拦截关闭事件，改为隐藏窗口而不是退出
        try:
            global _MAIN_WINDOW
            if _MAIN_WINDOW:
                _MAIN_WINDOW.hide()
                return False  # 返回False阻止默认的关闭行为
        except Exception:
            pass
        return True  # 如果隐藏失败，允许关闭

    # 绑定事件：尽量使用pywebview的标准事件，避免拦截过度
    try:
        window.events.closing += _on_closing
    except Exception:
        pass
    try:
        window.events.closed += _on_closed
    except Exception:
        pass

    # 注入 REST 服务基地址
    try:
        def _inject_api_base():
            try:
                if _REST_SERVER and _REST_SERVER.base_url:
                    js = (
                        f"window.__API_BASE__ = '{_REST_SERVER.base_url}';"
                        f"window.__APP_VERSION__ = '{APP_VERSION}';"
                        "console.log('[REST] BASE', window.__API_BASE__, 'VER', window.__APP_VERSION__);"
                    )
                    window.evaluate_js(js)
            except Exception:
                pass

        # 在页面 loaded 事件注入，确保可用
        try:
            def _on_loaded():
                _inject_api_base()
            window.events.loaded += _on_loaded
        except Exception:
            # 回退：定时器注入
            threading.Timer(0.8, _inject_api_base).start()
    except Exception:
        pass

    # Windows特定：使用pywin32拦截任务栏关闭
    try:
        if sys.platform.startswith("win"):
            import win32gui
            import win32con

            def wnd_proc(hwnd, msg, wparam, lparam):
                if msg == win32con.WM_CLOSE:
                    # 拦截关闭消息，隐藏窗口而不是退出
                    try:
        
                        if _MAIN_WINDOW:
                            _MAIN_WINDOW.hide()
                            return 0  # 返回0阻止默认处理
                    except Exception:
                        pass
                return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

            # 获取窗口句柄并设置自定义窗口过程
            def setup_window_hook():
                try:
                    # 等待窗口创建完成
                    import time
                    time.sleep(2)  # 等待2秒让窗口完全创建

                    # 查找窗口句柄（通过标题）
                    hwnd = win32gui.FindWindow(None, "Auto Homework")
                    if hwnd:
                        # 替换窗口过程
                        old_wnd_proc = win32gui.SetWindowLong(hwnd, win32con.GWL_WNDPROC, wnd_proc)
                        print(f"[Window] 已设置窗口钩子，句柄: {hwnd}")
                    else:
                        print("[Window] 未找到窗口句柄")
                except Exception as e:
                    print(f"[Window] 设置窗口钩子失败: {e}")

            # 在后台线程中设置窗口钩子
            import threading
            hook_thread = threading.Thread(target=setup_window_hook, daemon=True)
            hook_thread.start()

    except ImportError:
        print("[Window] pywin32不可用，跳过窗口钩子设置")
    except Exception as e:
        print(f"[Window] 设置窗口钩子时出错: {e}")

    # Windows上优先使用 EdgeChromium，如果不可用由pywebview自行回退
    gui = None
    if sys.platform.startswith("win"):
        gui = "edgechromium"

    # 启动前在控制台输出一次API可用性自检日志
    try:
        print("[Startup] 即将启动WebView。API桥已注册: ", isinstance(api_bridge, ApiBridge))
    except Exception:
        pass

    # 信号处理器已经在main函数开始时注册了，这里不需要重复注册

    # 启动GUI
    try:
        # 始终启用调试支持（F12 可用），但不自动打开 DevTools
        # 移除可能导致 Edge WebView2 自动打开 DevTools 的参数
        try:
            args = os.environ.get('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', '')
            if '--auto-open-devtools-for-tabs' in args:
                cleaned = ' '.join([a for a in args.split() if a != '--auto-open-devtools-for-tabs'])
                if cleaned.strip():
                    os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = cleaned
                else:
                    os.environ.pop('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', None)
        except Exception:
            pass
        # 关闭调试模式，禁用 DevTools
        webview.start(gui=gui, debug=False, http_server=True)
    except KeyboardInterrupt:
        print("\n[Signal] 捕获到KeyboardInterrupt，正在退出...")
        try:
            if _MAIN_WINDOW:
                _MAIN_WINDOW.destroy()
        except Exception as e:
            print(f"[Signal] 销毁窗口时出错: {e}")
        sys.exit(0)

def start_service_mode():
    """启动服务模式（后台运行）"""
    from service_mode import AutoHomeworkService
    import logging
    logging.basicConfig(level=logging.INFO)
    svc = AutoHomeworkService()
    svc.start()
def main():
    """主函数"""
    # 添加信号处理和退出处理
    import signal
    import sys
    import threading
    import atexit

    # 创建退出事件
    exit_event = threading.Event()

    def cleanup():
        """退出时清理函数"""
        print("\n[Exit] 正在清理资源...")
        try:
            instance_manager.cleanup()
        except Exception as e:
            print(f"[Exit] 清理时出错: {e}")

    def signal_handler(signum, frame):
        """处理信号"""
        print(f"\n[Signal] 收到信号 {signum}，正在退出...")
        exit_event.set()  # 设置退出事件
        # 尝试优雅退出
        try:
            if _MAIN_WINDOW:
                print("[Signal] 正在关闭窗口...")
                _MAIN_WINDOW.destroy()
        except Exception as e:
            print(f"[Signal] 销毁窗口时出错: {e}")
        print("[Signal] 正在退出应用...")
        sys.exit(0)

    # 注册退出处理函数
    atexit.register(cleanup)

    # 注册信号处理器
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        print("[Signal] 已注册信号处理器")
        print("[Info] 要退出应用，请使用设置页面中的'彻底退出'按钮")
    except (OSError, ValueError) as e:
        print(f"[Signal] 注册信号处理器失败: {e}")
        print("[Info] 信号处理不可用，请使用设置页面中的'彻底退出'按钮退出")

    # 启动优化
    try:
        from startup_optimizer import main as optimize_main
        optimize_main()
    except ImportError:
        print("启动优化器不可用，跳过优化步骤")

    # 检查单实例
    instance_manager = SingleInstanceManager()
    if not instance_manager.become_server():
        print("应用已在运行中，正在激活现有实例...")
        instance_manager.activate_existing_instance()
        sys.exit(0) # 客户端实例退出

    parser = argparse.ArgumentParser(description='Auto Homework 应用程序')
    parser.add_argument('--service', action='store_true',
                       help='以服务模式启动（后台运行，无GUI）')
    parser.add_argument('--ui', action='store_true',
                       help='以UI模式启动（默认）')

    args = parser.parse_args()

    try:
        # 如果指定了--service参数，启动服务模式
        if args.service:
            print("启动服务模式...")
            start_service_mode()
        else:
            # 默认启动UI模式
            print("启动UI模式...")
            start_ui_mode(instance_manager)
    except KeyboardInterrupt:
        print("\n[Signal] 捕获到KeyboardInterrupt，正在清理...")
        try:
            global _MAIN_WINDOW
            if _MAIN_WINDOW:
                _MAIN_WINDOW.destroy()
        except Exception as e:
            print(f"[Signal] 销毁窗口时出错: {e}")
    finally:
        # atexit 会处理 cleanup
        pass

if __name__ == "__main__":
    main()


