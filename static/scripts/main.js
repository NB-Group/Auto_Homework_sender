let currentFile = null;
let previewContent = null;
let lastLoadedConfig = null;

// API可用性检查（REST优先）
function checkApiAvailable() {
    if (!window.__API_BASE__) {
        // 固定端口兜底
        window.__API_BASE__ = 'http://127.0.0.1:58701';
    }
    return true;
}

// 等待API就绪
function waitForApi(timeout = 5000) {
    return new Promise((resolve, reject) => {
        const startTime = Date.now();
        let checkCount = 0;
        
        function check() {
            checkCount++;
            const elapsed = Date.now() - startTime;
            
            if (checkCount % 10 === 0) { // 每1秒打印一次状态
                console.log(`[waitForApi] 第${checkCount}次检查 (${elapsed}ms), REST:`, window.__API_BASE__, 'pywebview:', typeof pywebview !== 'undefined' ? 'defined' : 'undefined');
            }
            
            if (checkApiAvailable()) {
                console.log(`[waitForApi] API 可用！用时 ${elapsed}ms`);
                resolve(true);
            } else if (elapsed > timeout) {
                console.error(`[waitForApi] API 等待超时 ${elapsed}ms`);
                reject(new Error('API 等待超时'));
            } else {
                setTimeout(check, 100);
            }
        }
        
        console.log('[waitForApi] 开始等待 API，超时时间:', timeout + 'ms');
        check();
    });
}

// 确保调用的pywebview.api方法存在
function ensureApiMethod(methodName) {
    return typeof pywebview !== 'undefined' && pywebview.api && typeof pywebview.api[methodName] === 'function';
}

// 安全的最小化与关闭封装（HTML按钮使用）
async function appMinimize() {
    try {
        if (ensureApiMethod('minimize')) {
            await pywebview.api.minimize();
            return;
        }
    } catch (e) {
        console.warn('minimize API 调用失败', e);
    }
    // 回退：尝试隐藏窗口或失去焦点
    try { window.blur(); } catch (e) {}
}

async function appClose() {
    try {
        // 调用后端的close方法来隐藏窗口
        if (ensureApiMethod('close')) {
            await pywebview.api.close();
            return;
        }
    } catch (e) {
        console.warn('close API 调用失败', e);
    }
    // 回退：尝试最小化窗口
    try {
        if (window.blur) window.blur();
    } catch (e) {}
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    updateInteractiveBackground();
    
    // 检查API状态的函数
    function debugApiStatus() {
        console.log('=== API 状态检查 ===');
        console.log('window.pywebview:', typeof window.pywebview);
        console.log('pywebview (global):', typeof pywebview);
        if (typeof window.pywebview !== 'undefined') {
            console.log('window.pywebview.api:', window.pywebview.api);
        }
        if (typeof pywebview !== 'undefined') {
            console.log('pywebview.api:', pywebview.api);
            if (pywebview.api) {
                console.log('API 方法:', Object.keys(pywebview.api));
            }
        }
        console.log('==================');
    }

    // 等待API（使用固定端口REST）准备就绪
    function waitForPyWebView() {
        // 直接使用固定端口
        window.__API_BASE__ = window.__API_BASE__ || 'http://127.0.0.1:58701';
        console.log('API 已准备就绪', window.__API_BASE__);
        debugApiStatus();
        loadSettings();
        initTheme();
        checkSchedulerStatus();
        setInterval(checkSchedulerStatus, 30000);
    }
    
    // 绑定主按钮（兜底绑定）
    bindMainButton();
    // 显式绑定保存按钮，防止 onclick 丢失
    const saveBtn = document.getElementById('save-settings-btn');
    if (saveBtn && !saveBtn.__ah_bound){
        saveBtn.__ah_bound = true;
        saveBtn.addEventListener('click', (e)=>{
            e.preventDefault();
            e.stopPropagation();
            saveSettings();
        });
    }
    // 解析 webhook: 在输入时即时解析
    const tokenInput = document.getElementById('access-token');
    if (tokenInput && !tokenInput.__ah_parse_bound){
        tokenInput.__ah_parse_bound = true;
        const tryParse = () => {
            try {
                const v = tokenInput.value || '';
                if (v.includes('access_token=')){
                    const url = new URL(v);
                    const at = url.searchParams.get('access_token');
                    if (at){
                        tokenInput.value = at;
                        showSuccess('已解析 webhook 中的 access_token');
                    }
                }
            } catch(_){ }
        };
        tokenInput.addEventListener('input', tryParse);
        tokenInput.addEventListener('change', tryParse);
        // 初始值也解析一次
        setTimeout(tryParse, 0);
    }

    // 显式绑定取消按钮，确保动画关闭
    const cancelBtn = document.getElementById('cancel-settings-btn');
    if (cancelBtn && !cancelBtn.__ah_bound){
        cancelBtn.__ah_bound = true;
        cancelBtn.addEventListener('click', (e)=>{
            e.preventDefault();
            e.stopPropagation();
            cancelSettings();
        });
    }

    // 开始等待
    waitForPyWebView();

    // 兜底：无论是否就绪，1秒后先刷新一次状态，避免一直停留在“检查中”
    setTimeout(() => {
        try { checkSchedulerStatus(); } catch (e) { console.log('兜底状态刷新失败', e); }
        // 再次兜底绑定一次按钮（防止DOM晚渲染或被替换）
        try { bindMainButton(); } catch (e) { console.log('兜底按钮绑定失败', e); }
    }, 1000);

    // 绑定检查更新按钮
    const upd = document.getElementById('check-update-btn');
    if (upd && !upd.__bound){
        upd.__bound = true;
        upd.addEventListener('click', (e)=>{ e.preventDefault(); e.stopPropagation(); checkUpdateManually(); });
    }
});

// 监听 pywebview 原生 ready 事件，进一步增强兼容性
window.addEventListener('pywebviewready', function() {
    console.log('pywebviewready 事件触发');
    try {
        loadSettings();
        initTheme();
        checkSchedulerStatus();
        bindMainButton();
    } catch (e) { console.log('pywebviewready 初始化失败', e); }
});

// 兜底绑定首页大按钮点击事件
function bindMainButton(){
    const btn = document.querySelector('.main-send-btn');
    if (!btn){
        console.warn('未找到主按钮 .main-send-btn');
        return;
    }
    
    // 检查是否已绑定
    if (btn.__ah_bound){
        console.log('主按钮已经绑定过，跳过');
        return;
    }
    
    // 移除可能存在的HTML onclick属性
    btn.removeAttribute('onclick');
    
    // 显式可点击样式
    btn.style.cursor = 'pointer';
    btn.setAttribute('tabindex','0');
    
    // 绑定点击事件
    btn.addEventListener('click', (e)=>{
        console.log('主按钮点击');
        e.preventDefault();
        e.stopPropagation();
        selectAndPreview();
    });
    
    // 键盘无障碍：回车/空格触发
    btn.addEventListener('keydown', (e)=>{
        if (e.key === 'Enter' || e.key === ' '){
            console.log('主按钮键盘触发');
            e.preventDefault();
            e.stopPropagation();
            selectAndPreview();
        }
    });
    
    btn.__ah_bound = true;
    console.log('主按钮已绑定事件');
}

// 鼠标跟踪交互背景
function updateInteractiveBackground() {
    const interactive = document.querySelector('.interactive');
    if (!interactive) return;
    
    document.addEventListener('mousemove', (e) => {
        const x = (e.clientX / window.innerWidth) * 100;
        const y = (e.clientY / window.innerHeight) * 100;
        
        interactive.style.background = `radial-gradient(circle at ${x}% ${y}%, rgba(var(--color-interactive), 0.8) 0, rgba(var(--color-interactive), 0) 50%) no-repeat`;
    });
}

// 选择并预览PPT
let selectAndPreviewRunning = false;
async function selectAndPreview() {
    if (selectAndPreviewRunning) {
        console.log('[selectAndPreview] 已在运行中，跳过');
        return;
    }
    selectAndPreviewRunning = true;
    console.log('[selectAndPreview] start');
    
    // 强制探测一次 REST 基地址（通过 pywebview 后备）
    if (!window.__API_BASE__ && typeof pywebview !== 'undefined' && pywebview.api && typeof pywebview.api.get_rest_base === 'function') {
        try {
            const restInfo = await pywebview.api.get_rest_base();
            if (restInfo && restInfo.success && restInfo.base) {
                window.__API_BASE__ = restInfo.base;
                console.log('[REST] BASE(set via bridge)', window.__API_BASE__);
            }
        } catch (e) {
            console.warn('[REST] get_rest_base failed', e);
        }
    }
    console.log('[selectAndPreview] REST base:', window.__API_BASE__, '| pywebview:', typeof pywebview !== 'undefined');
    
    // 检查API是否可用
    if (!window.__API_BASE__ && (typeof pywebview === 'undefined' || !pywebview.api)) {
        console.log('[selectAndPreview] API 未就绪，开始等待...');
        // 再次尝试等待API就绪
        try { 
            await waitForApi(5000);
            console.log('[selectAndPreview] API 等待成功');
        } catch (e) {
            console.error('[selectAndPreview] API 等待失败:', e);
        }
        if (!window.__API_BASE__ && (typeof pywebview === 'undefined' || !pywebview.api)) {
            console.error('[selectAndPreview] API 仍然不可用');
            showError('应用程序接口未就绪，请稍后重试');
            selectAndPreviewRunning = false;
            return;
        }
    }
    
    // 检查是否有保存的PPT文件路径
    try {
        // 先测一发 ping，确认桥接可响应
        if (!ensureApiMethod('ping')) {
            await waitForApi(1000);
        }
        if (ensureApiMethod('ping')){
            try {
                const pong = await pywebview.api.ping();
                console.log('[selectAndPreview] ping result', pong);
            } catch (e) {
                console.warn('[selectAndPreview] ping 调用失败', e);
            }
        } else {
            console.warn('[selectAndPreview] ping 方法不可用');
        }

        // 通过 REST 获取配置
        if (window.__API_BASE__) {
            const resp = await fetch(`${window.__API_BASE__}/api/config`);
            const config = await resp.json();
            console.log('[selectAndPreview] get_config ok (REST)', config);
            if (config.ppt_file_path) {
                showLoading('加载保存的PPT文件...');
                const pr = await fetch(`${window.__API_BASE__}/api/preview_homework`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ file_path: config.ppt_file_path })});
                const previewResult = await pr.json();
                console.log('[selectAndPreview] preview with saved path result (REST)', previewResult);
                if (previewResult.success) {
                    currentFile = config.ppt_file_path; // 设置当前文件路径
                    previewContent = previewResult.content;
                    hideLoading();
                    showPreview(previewResult.content, previewResult.file_name);
                    return;
                } else {
                    hideLoading();
                    showError('解析PPT失败: ' + previewResult.error);
                }
            }
        } else {
            if (!ensureApiMethod('get_config')) {
                await waitForApi(2000);
                if (!ensureApiMethod('get_config')) throw new Error('get_config not available');
            }
            const config = await pywebview.api.get_config();
            console.log('[selectAndPreview] get_config ok', config);
            if (config.ppt_file_path) {
                showLoading('加载保存的PPT文件...');
                if (!ensureApiMethod('preview_homework')) {
                    await waitForApi(2000);
                    if (!ensureApiMethod('preview_homework')) throw new Error('preview_homework not available');
                }
                const previewResult = await pywebview.api.preview_homework(config.ppt_file_path);
                console.log('[selectAndPreview] preview with saved path result', previewResult);
                if (previewResult.success) {
                    previewContent = previewResult.content;
                    hideLoading();
                    showPreview(previewResult.content, previewResult.file_name);
                    return;
                } else {
                    hideLoading();
                    showError('解析PPT失败: ' + previewResult.error);
                }
            }
        }
    } catch (error) {
        console.log('无法使用保存的文件路径，继续选择新文件:', error);
    }
    
    showLoading('选择PPT文件...');
    
    try {
        if (!ensureApiMethod('select_ppt_file')) {
            await waitForApi(2000);
            if (!ensureApiMethod('select_ppt_file')) throw new Error('select_ppt_file not available');
        }
        let result;
        if (window.__API_BASE__) {
            const r = await fetch(`${window.__API_BASE__}/api/select_ppt_file`, { method:'POST' });
            result = await r.json();
        } else {
            result = await pywebview.api.select_ppt_file();
        }
        console.log('[selectAndPreview] file selected', result);
        
        if (result.success && result.file_path) {
            currentFile = result.file_path;
            updateStatus('正在解析PPT内容...');
            
            if (!ensureApiMethod('preview_homework')) {
                await waitForApi(2000);
                if (!ensureApiMethod('preview_homework')) throw new Error('preview_homework not available');
            }
            let previewResult;
            if (window.__API_BASE__) {
                const pr2 = await fetch(`${window.__API_BASE__}/api/preview_homework`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ file_path: currentFile })});
                previewResult = await pr2.json();
            } else {
                previewResult = await pywebview.api.preview_homework(currentFile);
            }
            console.log('[selectAndPreview] preview with new file result', previewResult);
            
            if (previewResult.success) {
                previewContent = previewResult.content;
                showPreview(previewResult.content, previewResult.file_name);
            } else {
                showError('解析PPT失败: ' + previewResult.error);
            }
        } else {
            updateStatus('未选择文件');
        }
    } catch (error) {
        showError('操作失败: ' + error.message);
    } finally {
        hideLoading();
        selectAndPreviewRunning = false;
    }
}

// 显示预览页面
function showPreview(content, fileName) {
    console.log('[showPreview] 开始显示预览:', fileName);
    const previewContentEl = document.getElementById('preview-content');
    
    // 将Markdown转换为HTML
    const htmlContent = markdownToHtml(content);
    previewContentEl.innerHTML = htmlContent;
    console.log('[showPreview] 内容已设置，长度:', htmlContent.length);
    
    // 更新标题
    document.querySelector('.preview-title').textContent = `预览: ${fileName}`;
    
    // 绑定确认发送按钮
    bindConfirmSendButton();
    
    // 切换到预览页面
    console.log('[showPreview] 即将切换到预览页面');
    switchPage('preview-page');
}

// 绑定确认发送按钮事件
function bindConfirmSendButton() {
    const btn = document.getElementById('confirm-send-btn');
    if (btn && !btn.__bound) {
        btn.__bound = true;
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('[confirmSend] 按钮点击');
            confirmSend();
        });
        console.log('[confirmSend] 按钮已绑定');
    }
}

// 简单的Markdown转HTML
function markdownToHtml(markdown) {
    return markdown
        .replace(/^# (.*$)/gm, '<h1>$1</h1>')
        .replace(/^## (.*$)/gm, '<h2>$1</h2>')
        .replace(/^### (.*$)/gm, '<h3>$1</h3>')
        .replace(/^\*\*(.*)\*\*$/gm, '<strong>$1</strong>')
        .replace(/^\*(.*)\*$/gm, '<em>$1</em>')
        .replace(/^---$/gm, '<hr>')
        .replace(/\n/g, '<br>');
}

// 确认发送
async function confirmSend() {
    console.log('[confirmSend] 开始发送, currentFile:', currentFile, 'previewContent:', !!previewContent);
    
    if (!previewContent) {
        showError('没有可发送的内容');
        return;
    }
    
    showLoading('正在发送到钉钉...');
    
    try {
        let result;
        if (window.__API_BASE__) {
            // 直接发送预览内容，不需要文件路径
            console.log('[confirmSend] 使用 REST API 发送内容');
            const response = await fetch(`${window.__API_BASE__}/api/send_content`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: previewContent })
            });
            console.log('[confirmSend] 响应状态:', response.status);
            result = await response.json();
            console.log('[confirmSend] 响应结果:', result);
        } else {
            // 回退到 pywebview
            console.log('[confirmSend] 使用 pywebview API 发送');
            if (!ensureApiMethod('send_homework')) throw new Error('send_homework not available');
            result = await pywebview.api.send_homework(currentFile);
        }
        
        if (result.success) {
            showSuccess('发送成功！');
            setTimeout(() => {
                goBack();
                updateStatus('发送完成');
            }, 2000);
        } else {
            showError('发送失败: ' + result.error);
        }
    } catch (error) {
        console.error('[confirmSend] 发送错误:', error);
        showError('发送失败: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 返回主页
function goBack() {
    switchPage('main-page');
    currentFile = null;
    previewContent = null;
    // 允许再次选择
    selectAndPreviewRunning = false;
}

// 页面切换（带动画的display控制）
function switchPage(pageId) {
    console.log('[switchPage] 切换到页面:', pageId);
    const pages = document.querySelectorAll('.page');
    let target = null;
    
    // 找到目标页面
    pages.forEach(page => {
        if (page.id === pageId) {
            target = page;
        }
    });
    
    if (!target) {
        console.error('[switchPage] 找不到页面:', pageId);
        return;
    }
    
    // 隐藏其他页面（带动画）
    pages.forEach(page => {
        if (page.id !== pageId && page.classList.contains('active')) {
            hidePageWithAnimation(page);
        }
    });
    
    // 显示目标页面（带动画）
    showPageWithAnimation(target);
}

// 显示页面（带动画）
function showPageWithAnimation(page) {
    page.classList.add('animating');
    page.style.display = 'flex';
    
    // 强制重绘，确保display生效
    page.offsetHeight;
    
    // 再次强制重绘，然后触发入场动画
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            page.classList.add('active');
            console.log('[switchPage] 页面已激活:', page.id);
            
            // 动画完成后清理animating类
            setTimeout(() => {
                page.classList.remove('animating');
            }, 500); // 与CSS transition时间一致
        });
    });
}

// 隐藏页面（带动画）
function hidePageWithAnimation(page) {
    page.classList.add('animating');
    page.classList.remove('active');
    
    // 动画完成后隐藏display
    setTimeout(() => {
        page.style.display = 'none';
        page.classList.remove('animating');
    }, 500); // 与CSS transition时间一致
}

// 显示设置
function showSettings() {
    const modal = document.getElementById('settings-modal');
    showModalWithAnimation(modal);
}

// 隐藏设置
function hideSettings() {
    const modal = document.getElementById('settings-modal');
    hideModalWithAnimation(modal);
}

// 显示模态框（带动画）
function showModalWithAnimation(modal) {
    modal.classList.add('animating');
    modal.style.display = 'flex';
    
    requestAnimationFrame(() => {
        modal.classList.add('active');
        
        setTimeout(() => {
            modal.classList.remove('animating');
        }, 300); // 与CSS transition时间一致
    });
}

// 隐藏模态框（带动画）
function hideModalWithAnimation(modal) {
    modal.classList.add('animating');
    // 先强制重排，再在下一帧移除 active，确保过渡被触发
    // 强制重排
    // eslint-disable-next-line no-unused-expressions
    modal.offsetHeight;
    // 下一帧再移除 active
    requestAnimationFrame(() => {
        modal.classList.remove('active');
    });

    // 使用 transitionend 确保动画真正结束后再隐藏
    const onEnd = (e) => {
        if (e && e.target !== modal) return; // 只关心 modal 自身的过渡
        if (e && e.propertyName && e.propertyName !== 'opacity') return; // 仅在不透明度过渡完成时处理
        try {
            modal.style.display = 'none';
            modal.classList.remove('animating');
        } finally {
            modal.removeEventListener('transitionend', onEnd);
        }
    };
    modal.addEventListener('transitionend', onEnd);

    // 兜底：若某些环境不触发 transitionend，按时隐藏
    setTimeout(() => {
        try {
            modal.style.display = 'none';
            modal.classList.remove('animating');
        } catch (_) {}
        modal.removeEventListener('transitionend', onEnd);
    }, 350);
}



// 加载设置
async function loadSettings() {
    try {
        let config = null;

        // 优先通过 REST 读取，避免桥接未就绪导致未加载
        if (window.__API_BASE__) {
            try {
                const resp = await fetch(`${window.__API_BASE__}/api/config`, { cache: 'no-store' });
                config = await resp.json();
            } catch (e) {
                console.warn('REST 获取配置失败，回退 pywebview', e);
            }
        }

        // 回退到 pywebview.api
        if (!config || (config.success === false && !config.access_token)) {
            if (typeof pywebview !== 'undefined' && pywebview.api && typeof pywebview.api.get_config === 'function') {
                try { config = await pywebview.api.get_config(); } catch (e) { console.warn('pywebview 获取配置失败', e); }
            }
        }

        if (!config) throw new Error('无法加载配置');

        // 记录最近一次成功加载/保存的配置，用于取消还原
        lastLoadedConfig = { ...config };

        document.getElementById('access-token').value = config.access_token || '';
        document.getElementById('ppt-file-path').value = config.ppt_file_path || '';

        // 处理新的调度时间设置
        document.getElementById('weekday-time').value = config.weekday_send_time || '05:00';
        document.getElementById('friday-time').value = config.friday_send_time || '15:00';

        // 兼容旧版本，如果没有新字段则使用旧字段
        if (!config.weekday_send_time && config.auto_send_time) {
            document.getElementById('weekday-time').value = config.auto_send_time;
        }
        if (!config.friday_send_time && config.auto_send_time) {
            document.getElementById('friday-time').value = config.auto_send_time;
        }

        document.getElementById('auto-enabled').checked = config.auto_send_enabled || false;

        // 新增选项
        const uiChk = document.getElementById('autostart-ui');
        const blurRange = document.getElementById('glass-blur-range');
        const opRange = document.getElementById('glass-opacity-range');
        const blurVal = document.getElementById('glass-blur-value');
        const opVal = document.getElementById('glass-opacity-value');

        if (uiChk) uiChk.checked = (config.auto_start_ui ?? true);
        if (blurRange) blurRange.value = (config.glass_blur ?? 20);
        if (opRange) opRange.value = (config.glass_opacity ?? 0.15);
        if (blurVal) blurVal.textContent = `${blurRange.value}px`;
        if (opVal) opVal.textContent = `${opRange.value}`;

        // 应用玻璃参数到 CSS 变量（仅在加载/保存时应用）
        applyGlassConfig(config);

        // 实时仅更新显示文本，不改动样式与配置
        if (blurRange) {
            blurRange.addEventListener('input', () => {
                const v = Number(blurRange.value || 20);
                document.getElementById('glass-blur-value').textContent = `${v}px`;
            });
        }
        if (opRange) {
            opRange.addEventListener('input', () => {
                const v = Number(opRange.value || 0.15);
                document.getElementById('glass-opacity-value').textContent = `${v}`;
            });
        }

        // 设置主题下拉框
        const theme = config.theme || 'dark';
        const themeText = theme === 'dark' ? '深色模式' : '浅色模式';
        document.getElementById('theme-select-text').textContent = themeText;
        updateThemeSelection(theme);

        // 加载开机启动状态（若桥接未就绪会自动跳过）
        await loadAutostartStatus();

        console.log('设置加载成功:', config);
    } catch (error) {
        console.error('加载设置失败:', error);
    }
}

// 加载开机启动状态
async function loadAutostartStatus() {
    try {
    if (typeof pywebview === 'undefined' || !pywebview.api || !ensureApiMethod('get_autostart_status')) {
            console.log('开机启动API不可用');
            return;
        }

    const status = await pywebview.api.get_autostart_status();

        // 更新UI显示
        updateAutostartStatusDisplay(status);

        console.log('开机启动状态加载成功:', status);
    } catch (error) {
        console.error('加载开机启动状态失败:', error);
    }
}

// 更新开机启动状态显示
function updateAutostartStatusDisplay(status) {
    const uiStatusEl = document.getElementById('autostart-ui-status');

    if (uiStatusEl) {
        uiStatusEl.textContent = status.ui_autostart ? '已启用' : '未启用';
        uiStatusEl.className = status.ui_autostart ? 'status-enabled' : 'status-disabled';
    }
}

// 保存设置
async function saveSettings() {
    const themeValue = document.querySelector('.custom-select-option.selected')?.dataset?.value || 'dark';

    let accessToken = document.getElementById('access-token').value || '';
    // 解析 webhook 链接
    try {
        if (typeof accessToken === 'string' && accessToken.includes('access_token=')) {
            const url = new URL(accessToken);
            const at = url.searchParams.get('access_token');
            if (at) accessToken = at;
        }
    } catch (_) {}

    const config = {
        access_token: accessToken,
        ppt_file_path: document.getElementById('ppt-file-path').value,
        // 新的调度时间设置
        weekday_send_time: document.getElementById('weekday-time').value,
        friday_send_time: document.getElementById('friday-time').value,
        // 保持向后兼容
        auto_send_time: document.getElementById('weekday-time').value,
        auto_send_enabled: document.getElementById('auto-enabled').checked,
        theme: themeValue,
        auto_start_ui: document.getElementById('autostart-ui')?.checked ?? true,
        glass_blur: Number(document.getElementById('glass-blur-range')?.value || 20),
        glass_opacity: Number(document.getElementById('glass-opacity-range')?.value || 0.15)
    };

    try {
        let result = null;
        
        // 优先通过 REST 保存配置
        if (window.__API_BASE__) {
            try {
                const resp = await fetch(`${window.__API_BASE__}/api/config`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                    cache: 'no-store',
                    body: JSON.stringify(config)
                });
                // 优先使用HTTP状态判断
                if (resp.ok) {
                    try {
                        result = await resp.json();
                    } catch (_) {
                        result = { success: true };
                    }
                } else {
                    try {
                        const errJson = await resp.json();
                        result = { success: false, error: errJson?.error || `HTTP ${resp.status}` };
                    } catch (_e) {
                        result = { success: false, error: `HTTP ${resp.status}` };
                    }
                }
            } catch (e) {
                console.warn('REST 保存配置失败，回退 pywebview', e);
            }
        }
        
        // 回退到 pywebview.api
        if (!result || (result.success === false && !result.error)) {
            if (!ensureApiMethod('save_config')) throw new Error('save_config not available');
            result = await pywebview.api.save_config(config);
        }

        if (result && result.success !== false) {
            showSuccess('设置保存成功');
            applyTheme(config.theme);
            applyGlassConfig(config);
            // 更新最近一次配置为已保存版本
            lastLoadedConfig = { ...config };

            // 重新加载开机启动状态
            await loadAutostartStatus();

            // 若注册表权限失败，尝试告知用户
            try {
                if (result.error && /权限|注册表|Registry|PERMISSION/i.test(result.error)) {
                    showError('开机自启写入失败：可能需要以管理员权限运行');
                }
            } catch(_) {}

            // 成功后带动画关闭
            hideSettings();
        } else {
            const err = result.error || '保存失败';
            showError(err);
        }
    } catch (error) {
        showError('保存失败: ' + error.message);
    }
}

// 取消设置：还原至最近一次加载/保存的配置，并关闭设置窗口
function cancelSettings() {
    try {
        if (lastLoadedConfig) {
            const lc = lastLoadedConfig;
            document.getElementById('access-token').value = lc.access_token || '';
            document.getElementById('ppt-file-path').value = lc.ppt_file_path || '';
            document.getElementById('weekday-time').value = lc.weekday_send_time || lc.auto_send_time || '17:00';
            document.getElementById('friday-time').value = lc.friday_send_time || lc.auto_send_time || '15:00';
            document.getElementById('auto-enabled').checked = !!lc.auto_send_enabled;
            const blurRange = document.getElementById('glass-blur-range');
            const opRange = document.getElementById('glass-opacity-range');
            if (blurRange) {
                blurRange.value = (lc.glass_blur ?? 20);
                document.getElementById('glass-blur-value').textContent = `${blurRange.value}px`;
            }
            if (opRange) {
                opRange.value = (lc.glass_opacity ?? 0.15);
                document.getElementById('glass-opacity-value').textContent = `${opRange.value}`;
            }
            // 还原样式
            applyGlassConfig(lc);
        }
    } catch (e) {
        console.warn('取消设置还原失败', e);
    } finally {
        hideSettings();
    }
}

// 根据配置应用玻璃参数
function applyGlassConfig(cfg){
    const root = document.documentElement;
    const blur = Math.max(0, Math.min(60, Number(cfg.glass_blur ?? 20)));
    const opacity = Math.max(0, Math.min(1, Number(cfg.glass_opacity ?? 0.15)));

    // 设置模糊半径（需要px单位）
    root.style.setProperty('--glass-blur', `${blur}px`);
    root.style.setProperty('--glass-bg-opacity', `${opacity}`);

    // 强制刷新样式
    document.body.style.display = 'none';
    document.body.offsetHeight; // 触发重排
    document.body.style.display = '';

    console.log(`Glass config applied: blur=${blur}px, opacity=${opacity}`);
}

// 显示加载状态
function showLoading(text = '处理中...') {
    const loading = document.getElementById('loading');
    const loadingText = document.querySelector('.loading-text');
    loadingText.textContent = text;
    loading.classList.add('active');
    console.log('[loading] show:', text);
}

// 隐藏加载状态
function hideLoading() {
    const loading = document.getElementById('loading');
    loading.classList.remove('active');
    console.log('[loading] hide');
}

// 更新状态文本
function updateStatus(text) {
    const statusText = document.getElementById('status-text');
    statusText.textContent = text;
}

// 显示成功消息
function showSuccess(message) {
    updateStatus(message);
    const statusIndicator = document.querySelector('.status-indicator');
    statusIndicator.classList.add('animate-success');
    
    setTimeout(() => {
        statusIndicator.classList.remove('animate-success');
    }, 1000);
}

// 显示错误消息
function showError(message) {
    updateStatus(message);
    const statusIndicator = document.querySelector('.status-indicator');
    statusIndicator.classList.add('animate-error');
    
    setTimeout(() => {
        statusIndicator.classList.remove('animate-error');
    }, 500);
}

// 检查调度器状态
async function checkSchedulerStatus() {
    try {
        // 使用 REST API 获取调度器状态
        if (window.__API_BASE__) {
            const resp = await fetch(`${window.__API_BASE__}/api/scheduler/status`, { cache: 'no-store' });
            const status = await resp.json();
            updateSchedulerStatus(status);
        } else {
            // 回退到 pywebview（应该不会到这里）
            if (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.get_scheduler_status) {
                const status = await Promise.race([
                    pywebview.api.get_scheduler_status(),
                    new Promise((resolve) => setTimeout(() => resolve({
                        auto_send_enabled: false,
                        scheduler_running: false,
                        next_run: 'Unknown'
                    }), 2000))
                ]);
                updateSchedulerStatus(status);
            } else {
                updateSchedulerStatus({
                    auto_send_enabled: false,
                    scheduler_running: false
                });
            }
        }
    } catch (error) {
        console.log('调度器状态检查失败:', error);
        const schedulerInfo = document.getElementById('scheduler-info');
        if (schedulerInfo) {
            schedulerInfo.textContent = '⚠️ 状态检查失败';
        }
        setTimeout(() => {
            try { checkSchedulerStatus(); } catch (e) {}
        }, 2000);
    }
}

// 更新调度器状态显示
function updateSchedulerStatus(status) {
    const schedulerInfo = document.getElementById('scheduler-info');
    if (!schedulerInfo) return;

    let statusText = '';
    if (status.auto_send_enabled) {
        if (status.scheduler_running) {
            statusText = `🟢 自动发送运行中 - ${status.current_weekday} ${status.current_time}`;
            if (status.next_run && status.next_run !== 'None') {
                try {
                    const nextRun = new Date(status.next_run);
                    if (!isNaN(nextRun.getTime())) {
                        statusText += ` | 下次: ${nextRun.toLocaleString('zh-CN', {
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit'
                        })}`;
                    }
                } catch (e) {
                    // 忽略日期解析错误
                }
            }
            // 显示不同日期的发送时间
            if (status.weekday_send_time && status.friday_send_time) {
                statusText += `\n周一-四: ${status.weekday_send_time} | 周五: ${status.friday_send_time}`;
            }
        } else {
            statusText = `🔴 自动发送已启用但调度器未运行`;
        }
    } else {
        statusText = `⚪ 自动发送未启用`;
    }

    schedulerInfo.innerHTML = statusText.replace('\n', '<br>');
    console.log('调度器状态已更新:', statusText);
}

// 键盘快捷键
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        cancelSettings();
        if (document.getElementById('preview-page').classList.contains('active')) {
            goBack();
        }
    }
});

// 选择PPT文件
async function selectPPTFile() {
    try {
        if (typeof pywebview === 'undefined' || !pywebview.api) {
            showError('应用程序接口未就绪');
            return;
        }
        
        const result = await pywebview.api.select_ppt_file();
        if (result.success && result.file_path) {
            document.getElementById('ppt-file-path').value = result.file_path;
        }
    } catch (error) {
        showError('选择文件失败: ' + error.message);
    }
}

// 手动检查更新
async function checkUpdateManually(){
    try{
        if(!window.__API_BASE__) return showError('本地服务未就绪');
        const r = await fetch(`${window.__API_BASE__}/api/update/check`);
        const j = await r.json();
        if(!j.success) return showError('更新检查失败: '+ (j.error||''));
        const latest = (j.latest || '0.0.0').replace(/^v/i,'');
        const cur = (window.__APP_VERSION__ || '0.0.0').replace(/^v/i,'');
        if(latest !== cur){
            // 弹窗提示并提供镜像
            const url = j.download || '';
            const mirrors = Array.isArray(j.mirrors)? j.mirrors : [];
            const first = mirrors[0] || url;
            showSuccess(`发现新版本 ${latest}`);
            setTimeout(()=>{ try{ window.open(first || url, '_blank'); }catch(_){} }, 600);
        }else{
            showSuccess('当前已是最新版本');
        }
    }catch(e){
        showError('更新检查失败: '+e.message);
    }
}

// 开机自动检查一次（延迟几秒）
setTimeout(()=>{ try{ checkUpdateManually(); }catch(_){ } }, 3000);

// 主题相关函数
let currentTheme = 'dark';

function initTheme() {
    // 从设置中加载主题，如果没有则使用默认深色主题
    if (typeof pywebview !== 'undefined' && pywebview.api) {
        pywebview.api.get_config().then(config => {
            const theme = config.theme || 'dark';
            currentTheme = theme;
            applyTheme(theme);
            console.log('主题初始化成功:', theme);
        }).catch((error) => {
            console.log('主题初始化失败，使用默认主题:', error);
            currentTheme = 'dark';
            applyTheme('dark');
        });
    } else {
        console.log('PyWebView API 不可用，使用默认主题');
        currentTheme = 'dark';
        applyTheme('dark');
    }
}

function applyTheme(theme) {
    currentTheme = theme;
    document.documentElement.setAttribute('data-theme', theme);
}

// 自定义下拉框功能
function toggleThemeSelect() {
    const button = document.querySelector('.custom-select-button');
    const dropdown = document.getElementById('theme-select-dropdown');
    
    button.classList.toggle('active');
    dropdown.classList.toggle('active');
}

function selectTheme(value, text) {
    currentTheme = value;
    document.getElementById('theme-select-text').textContent = text;
    updateThemeSelection(value);
    toggleThemeSelect();
    applyTheme(value);
}

function updateThemeSelection(value) {
    const options = document.querySelectorAll('.custom-select-option');
    options.forEach(option => {
        option.classList.toggle('selected', option.dataset.value === value);
    });
}

// 点击外部关闭下拉框
document.addEventListener('click', function(e) {
    const themeSelect = document.getElementById('theme-select');
    const modal = document.getElementById('settings-modal');
    
    if (!themeSelect.contains(e.target)) {
        const button = document.querySelector('.custom-select-button');
        const dropdown = document.getElementById('theme-select-dropdown');
        button.classList.remove('active');
        dropdown.classList.remove('active');
    }
    
    if (e.target === modal) {
        cancelSettings();
    }
});

// 彻底退出应用
async function exitApplication() {
    try {
        if (typeof pywebview === 'undefined' || !pywebview.api) {
            showError('应用程序接口未就绪');
            return;
        }

        // 显示确认对话框
        if (!confirm('确定要彻底退出应用程序吗？这将停止所有后台任务。')) {
            return;
        }

        showLoading('正在退出...');

        if (!ensureApiMethod('exit_app')) throw new Error('exit_app not available');
        const result = await pywebview.api.exit_app();

        if (!result.success) {
            hideLoading();
            showError('退出失败: ' + result.error);
        }
        // 如果成功，应用会直接退出，不需要隐藏加载状态
    } catch (error) {
        hideLoading();
        showError('退出失败: ' + error.message);
    }
}

// 主题切换监听器 - 删除原来的，因为现在使用自定义下拉框
