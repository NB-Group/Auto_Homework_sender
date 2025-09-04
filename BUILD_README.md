# 打包说明文档

## 打包工具对比

### 1. Nuitka (⭐推荐⭐)
**优点:**
- 启动速度最快 (几乎原生Python速度)
- 体积相对较小
- 真正的编译，不是打包

**缺点:**
- 编译时间较长
- 某些复杂依赖可能需要额外配置

**使用方法:**
```bash
pip install nuitka
python build_nuitka.py
```

### 2. cx_Freeze
**优点:**
- 对pywebview支持很好
- 启动速度快
- 配置相对简单

**缺点:**
- 体积比Nuitka稍大
- Windows下需要手动处理一些DLL

**使用方法:**
```bash
pip install cx_Freeze
python setup_cx_freeze.py build
```

### 3. auto-py-to-exe
**优点:**
- 图形化界面，使用简单
- 基于PyInstaller但优化了参数
- 可以保存配置

**缺点:**
- 启动速度仍然不如前两者
- 体积较大

**使用方法:**
```bash
pip install auto-py-to-exe
auto-py-to-exe
```

### 4. 优化的PyInstaller
**优点:**
- 兼容性最好
- 社区支持最多

**缺点:**
- 启动速度慢
- 体积最大

## 推荐的打包流程

### 第一选择: Nuitka
```bash
# 1. 安装Nuitka
pip install nuitka

# 2a. 运行打包脚本 (EdgeChromium后端 - 推荐)
python build_nuitka.py

# 2b. 或者使用MSHTML后端 (更稳定，兼容性更好)
python build_nuitka_mshtml.py

# 3. 等待编译完成 (可能需要5-15分钟)
# 4. 在dist目录找到AutoHomework.exe
```

**注意：** 
- EdgeChromium后端需要安装Microsoft Edge WebView2 Runtime
- MSHTML后端使用Windows内置的IE引擎，兼容性更好
- 如果EdgeChromium版本失败，请尝试MSHTML版本

### 第二选择: cx_Freeze
```bash
# 1. 安装cx_Freeze
pip install cx_Freeze

# 2. 运行打包
python setup_cx_freeze.py build

# 3. 在build目录找到可执行文件
```

### 第三选择: 批处理脚本
```bash
# 直接运行批处理脚本，选择打包方式
build.bat
```

## 打包注意事项

1. **确保所有依赖都已安装**
   ```bash
   pip install -r requirements.txt
   ```

2. **检查static目录结构**
   - 确保static目录包含所有前端文件
   - HTML、CSS、JS文件都要完整

3. **测试可执行文件**
   - 在干净的系统上测试
   - 检查是否需要额外的运行时库

4. **文件大小优化**
   - 移除不必要的依赖
   - 使用--exclude-module排除不需要的模块

## 常见问题解决

### 问题1: 启动慢
- 不要使用PyInstaller单文件模式
- 使用Nuitka或cx_Freeze
- 排除不必要的模块

### 问题2: 文件过大
- 使用exclude参数排除测试模块
- 考虑使用目录模式而非单文件模式

### 问题3: 依赖缺失
- 检查hidden-import设置
- 手动复制缺失的DLL文件

### 问题4: tkinter问题
- 确保正确包含tkinter模块
- 在Nuitka中使用--plugin-enable=tk-inter

## 最终建议

为了获得最佳的启动速度和用户体验，建议按以下顺序尝试：

1. **Nuitka** - 如果编译成功，启动速度最快
2. **cx_Freeze** - 如果Nuitka有问题，这是很好的备选
3. **auto-py-to-exe** - 如果需要图形化配置界面
4. **PyInstaller** - 只在其他方案都不可行时使用
