# Auto Homework Sender 高级安装程序构建脚本
# PowerShell 版本，支持更多自定义选项

param(
    [switch]$Help,
    [switch]$Clean,
    [switch]$Build,
    [switch]$Test,
    [string]$Version = "1.0.0"
)

# 设置控制台编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Show-Header {
    Write-Host "===============================================" -ForegroundColor Cyan
    Write-Host "   Auto Homework Sender 安装程序构建工具" -ForegroundColor Yellow
    Write-Host "               PowerShell 版本" -ForegroundColor Green
    Write-Host "===============================================" -ForegroundColor Cyan
    Write-Host ""
}

function Show-Help {
    Write-Host "用法：" -ForegroundColor Yellow
    Write-Host "  .\build_installer.ps1 [选项]" -ForegroundColor White
    Write-Host ""
    Write-Host "选项：" -ForegroundColor Yellow
    Write-Host "  -Help          显示此帮助信息" -ForegroundColor White
    Write-Host "  -Clean         清理构建文件" -ForegroundColor White
    Write-Host "  -Build         构建安装程序" -ForegroundColor White
    Write-Host "  -Test          构建后自动测试" -ForegroundColor White
    Write-Host "  -Version       指定版本号 (默认: 1.0.0)" -ForegroundColor White
    Write-Host ""
    Write-Host "示例：" -ForegroundColor Yellow
    Write-Host "  .\build_installer.ps1 -Build -Test" -ForegroundColor Green
    Write-Host "  .\build_installer.ps1 -Clean -Build -Version '1.1.0'" -ForegroundColor Green
}

function Test-Prerequisites {
    Write-Host "[检查] 验证系统环境..." -ForegroundColor Blue
    
    # 检查Inno Setup
    $isccPath = Get-Command "iscc.exe" -ErrorAction SilentlyContinue
    if (-not $isccPath) {
        Write-Host "[错误] 未找到 Inno Setup 编译器" -ForegroundColor Red
        Write-Host ""
        Write-Host "请安装 Inno Setup：" -ForegroundColor Yellow
        Write-Host "1. 访问 https://jrsoftware.org/isinfo.php"
        Write-Host "2. 下载并安装 Inno Setup"
        Write-Host "3. 确保安装路径已添加到系统 PATH"
        return $false
    }
    
    # 检查应用程序文件
    if (-not (Test-Path "dist_nuitka\main.exe")) {
        Write-Host "[错误] 未找到应用程序文件 dist_nuitka\\main.exe" -ForegroundColor Red
        Write-Host "请先运行: python complete_build.py 或 python build_auto.py" -ForegroundColor Yellow
        return $false
    }
    
    # 检查必要文件
    $requiredFiles = @("icon.ico", "LICENSE.txt", "installer_setup.iss")
    foreach ($file in $requiredFiles) {
        if (-not (Test-Path $file)) {
            Write-Host "[错误] 未找到必要文件: $file" -ForegroundColor Red
            return $false
        }
    }
    
    Write-Host "[成功] 所有必要文件检查完成" -ForegroundColor Green
    return $true
}

function Invoke-Clean {
    Write-Host "[清理] 清理旧的构建文件..." -ForegroundColor Blue
    
    if (Test-Path "installer") {
        Remove-Item "installer" -Recurse -Force
        Write-Host "[清理] 删除 installer 目录" -ForegroundColor Yellow
    }
    
    if (Test-Path "dist") {
        $choice = Read-Host "[询问] 是否删除 dist 目录？(y/N)"
        if ($choice -eq 'y' -or $choice -eq 'Y') {
            Remove-Item "dist" -Recurse -Force
            Write-Host "[清理] 删除 dist 目录" -ForegroundColor Yellow
        }
    }
    
    Write-Host "[完成] 清理完成" -ForegroundColor Green
}

function Invoke-Build {
    Write-Host "[构建] 开始构建安装程序..." -ForegroundColor Blue
    
    # 创建输出目录
    if (-not (Test-Path "installer")) {
        New-Item -ItemType Directory -Path "installer" | Out-Null
        Write-Host "[信息] 创建安装程序输出目录" -ForegroundColor Yellow
    }
    
    # 更新版本号
    $issContent = Get-Content "installer_setup.iss" -Raw
    $issContent = $issContent -replace '#define MyAppVersion ".*"', "#define MyAppVersion `"$Version`""
    Set-Content "installer_setup.iss" -Value $issContent
    
    Write-Host "[信息] 版本号设置为: $Version" -ForegroundColor Green
    
    # 编译安装程序
    $startTime = Get-Date
    Write-Host "[构建] 正在编译安装程序..." -ForegroundColor Blue
    
    $process = Start-Process -FilePath "iscc.exe" -ArgumentList "installer_setup.iss" -Wait -PassThru -NoNewWindow
    
    $endTime = Get-Date
    $duration = $endTime - $startTime
    
    if ($process.ExitCode -eq 0) {
        Write-Host ""
        Write-Host "===============================================" -ForegroundColor Green
        Write-Host "            构建成功完成！" -ForegroundColor Yellow
        Write-Host "===============================================" -ForegroundColor Green
        Write-Host ""
        
        $installerFiles = Get-ChildItem "installer\AutoHomework_Setup_*.exe"
        foreach ($file in $installerFiles) {
            $size = [math]::Round($file.Length / 1MB, 2)
            Write-Host "生成文件: $($file.Name) ($size MB)" -ForegroundColor Green
        }
        
        Write-Host ""
        Write-Host "构建时间: $($duration.TotalSeconds.ToString('F1')) 秒" -ForegroundColor Blue
        Write-Host ""
        Write-Host "功能特性：" -ForegroundColor Yellow
        Write-Host "  ✓ 现代化安装界面" -ForegroundColor Green
        Write-Host "  ✓ 开机自启动选项" -ForegroundColor Green
        Write-Host "  ✓ 桌面快捷方式" -ForegroundColor Green
        Write-Host "  ✓ 开始菜单项目" -ForegroundColor Green
        Write-Host "  ✓ 完整卸载支持" -ForegroundColor Green
        Write-Host "  ✓ 中文界面支持" -ForegroundColor Green
        
        return $true
    } else {
        Write-Host ""
        Write-Host "[错误] 安装程序构建失败 (退出码: $($process.ExitCode))" -ForegroundColor Red
        return $false
    }
}

function Invoke-Test {
    Write-Host "[测试] 准备测试安装程序..." -ForegroundColor Blue
    
    $installerFiles = Get-ChildItem "installer\AutoHomework_Setup_*.exe"
    if ($installerFiles.Count -eq 0) {
        Write-Host "[错误] 未找到安装程序文件" -ForegroundColor Red
        return
    }
    
    $choice = Read-Host "[询问] 是否立即运行安装程序进行测试？(y/N)"
    if ($choice -eq 'y' -or $choice -eq 'Y') {
        $installerPath = $installerFiles[0].FullName
        Write-Host "[测试] 启动安装程序: $($installerFiles[0].Name)" -ForegroundColor Green
        Start-Process -FilePath $installerPath
    }
}

function Show-PostBuild {
    Write-Host ""
    Write-Host "后续步骤：" -ForegroundColor Yellow
    Write-Host "1. 测试安装程序在干净系统上的运行" -ForegroundColor White
    Write-Host "2. 验证开机自启动功能" -ForegroundColor White
    Write-Host "3. 测试完整的安装和卸载流程" -ForegroundColor White
    Write-Host "4. 检查所有快捷方式和注册表项" -ForegroundColor White
    Write-Host ""
    
    $choice = Read-Host "[询问] 是否打开安装程序目录？(y/N)"
    if ($choice -eq 'y' -or $choice -eq 'Y') {
        explorer "installer"
    }
}

# 主程序逻辑
Show-Header

if ($Help) {
    Show-Help
    exit
}

if (-not (Test-Prerequisites)) {
    Write-Host ""
    Write-Host "按任意键退出..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

$success = $true

if ($Clean) {
    Invoke-Clean
}

if ($Build -or (-not $Clean -and -not $Test -and -not $Help)) {
    $success = Invoke-Build
}

if ($Test -and $success) {
    Invoke-Test
}

if ($success) {
    Show-PostBuild
}

Write-Host ""
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
