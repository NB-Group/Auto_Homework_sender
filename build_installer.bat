@echo off
chcp 65001 > nul
echo ===============================================
echo   Auto Homework Sender 安装程序构建工具
echo ===============================================
echo.

:: 检查Inno Setup是否安装
where iscc.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Inno Setup 编译器 ^(iscc.exe^)
    echo.
    echo 请先安装 Inno Setup:
    echo 1. 访问 https://jrsoftware.org/isinfo.php
    echo 2. 下载并安装 Inno Setup
    echo 3. 确保安装路径已添加到系统 PATH
    echo.
    pause
    exit /b 1
)

echo [信息] 正在检查必要文件...

:: 检查应用程序是否已构建
if not exist "dist\main.dist\AutoHomework.exe" (
    echo [错误] 未找到应用程序文件 dist\main.dist\AutoHomework.exe
    echo.
    echo 请先运行 build_release.py 构建应用程序：
    echo python build_release.py
    echo.
    pause
    exit /b 1
)

:: 检查必要文件
if not exist "icon.ico" (
    echo [错误] 未找到图标文件 icon.ico
    pause
    exit /b 1
)

if not exist "LICENSE.txt" (
    echo [错误] 未找到许可协议文件 LICENSE.txt
    pause
    exit /b 1
)

echo [信息] 所有必要文件检查完成

:: 创建安装程序输出目录
if not exist "installer" (
    mkdir installer
    echo [信息] 创建安装程序输出目录
)

echo.
echo [信息] 开始构建安装程序...
echo.

:: 编译安装程序
iscc.exe installer_setup.iss

if %errorlevel% equ 0 (
    echo.
    echo ===============================================
    echo            构建完成！
    echo ===============================================
    echo.
    echo 安装程序已生成：
    for %%f in (installer\AutoHomework_Setup_*.exe) do echo   %%f
    echo.
    echo 功能特性：
    echo   ✓ 现代化安装界面
    echo   ✓ 开机自启动选项
    echo   ✓ 桌面快捷方式
    echo   ✓ 开始菜单项目
    echo   ✓ 完整卸载支持
    echo   ✓ 中文界面支持
    echo.
    
    choice /c YN /m "是否打开安装程序目录"
    if !errorlevel! equ 1 (
        explorer installer
    )
    
    echo.
    choice /c YN /m "是否立即测试安装程序"
    if !errorlevel! equ 1 (
        for %%f in (installer\AutoHomework_Setup_*.exe) do start "" "%%f"
    )
) else (
    echo.
    echo [错误] 安装程序构建失败
    echo 请检查 installer_setup.iss 文件中的配置
    echo.
    pause
)

echo.
echo 按任意键退出...
pause > nul
