# 自动作业助手 - 开机启动功能使用说明

## 功能介绍

自动作业助手支持两种开机启动模式：

1. **UI开机启动**：开机时自动启动主界面
2. **服务开机启动**：开机时自动启动后台服务（无界面，定时任务仍运行）

## 使用方法

### 方法一：通过设置界面配置（推荐）

1. 运行主程序 `main.py`
2. 点击右上角设置按钮（⚙️）
3. 在"开机自启"部分：
   - 勾选"开机启动主界面"：启用UI开机启动
   - 勾选"开机启动后台服务"：启用服务开机启动
4. 点击"保存设置"

设置保存后，开机启动项会自动配置到Windows注册表中。

### 方法二：使用命令行脚本

运行 `setup_autostart.py` 脚本：

```bash
# 查看当前状态
python setup_autostart.py --status

# 设置UI开机启动
python setup_autostart.py --setup-ui

# 移除UI开机启动
python setup_autostart.py --remove-ui

# 设置服务开机启动
python setup_autostart.py --setup-service

# 移除服务开机启动
python setup_autostart.py --remove-service

# 设置所有开机启动
python setup_autostart.py --setup-all

# 移除所有开机启动
python setup_autostart.py --remove-all
```

### 方法三：使用批处理文件

直接运行 `setup_autostart.bat`：

```cmd
# 查看状态
setup_autostart.bat --status

# 设置所有开机启动
setup_autostart.bat --setup-all

# 移除所有开机启动
setup_autostart.bat --remove-all
```

## 启动模式说明

### UI模式启动

- 运行 `main.py`（默认模式）
- 启动后显示主界面
- 用户可以进行所有操作

### 服务模式启动

- 运行 `main.py --service`
- 后台运行，不显示界面
- 定时任务正常执行
- 适合服务器环境或无人值守场景

## 注意事项

1. **权限要求**：设置开机启动需要管理员权限
2. **注册表操作**：开机启动项保存在 `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`
3. **日志记录**：所有操作都会记录在 `logs/` 目录下
4. **兼容性**：仅支持Windows系统
5. **路径处理**：开发环境和打包环境自动适配路径

## 故障排除

### 无法设置开机启动

1. 检查是否有管理员权限
2. 查看日志文件 `logs/setup_autostart_*.log`
3. 尝试手动运行脚本：`python setup_autostart.py --status`

### 开机启动无效

1. 检查注册表项是否存在：
   - 按 `Win + R`，输入 `regedit`
   - 导航到 `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`
   - 查看 `AutoHomework_UI` 和 `AutoHomework_Service` 项

2. 检查Python路径是否正确
3. 查看Windows事件查看器中的错误信息

### 日志文件位置

- 服务模式日志：`logs/service_YYYYMMDD.log`
- 设置脚本日志：`logs/setup_autostart_PID.log`

## 开发环境测试

如果在开发环境中测试，可以：

1. 直接运行：`python main.py --service`
2. 或者使用脚本：`python setup_autostart.py --setup-service`

注意：开发环境下路径会自动适配Python解释器。






