/**
 * 简历投递交互 — Modal + Toast
 * - 10秒自动弹出 Toast 提示
 * - 按钮点击打开 Modal 上传表单
 * - 已投递用户不弹出 Toast
 */
(function() {
    'use strict';

    const TOAST_DELAY = 10000;
    const STORAGE_KEY = 'resume_submitted';
    const SESSION_KEY = 'resume_toast_closed';

    const toast = document.getElementById('resumeToast');
    const modalOverlay = document.getElementById('resumeModalOverlay');
    const openBtn = document.getElementById('openResumeModalBtn');
    const closeBtn = document.getElementById('closeResumeModal');
    const dismissBtn = document.getElementById('dismissToast');
    const toastActionBtn = document.getElementById('toastActionBtn');
    const form = document.getElementById('modalResumeForm');
    const submitBtn = document.getElementById('modalSubmitBtn');
    const resultDiv = document.getElementById('modalResult');
    const sideCardBtn = document.getElementById('openResumeModalBtn');
    const submittedIndicator = document.getElementById('submittedIndicator');

    let toastTimer = null;
    let toastClosed = false;
    let _serverChecked = false;     // 是否已完成服务端状态同步
    let _isSubmitted = false;       // 真实的投递状态（服务端为准）

    // ---- 辅助函数 ----
    function isSubmitted() {
        return _isSubmitted;
    }

    function markSubmitted() {
        _isSubmitted = true;
        localStorage.setItem(STORAGE_KEY, '1');
        updateResumeUI();
        hideToast();
        closeModal();
    }

    function updateResumeUI() {
        if (_isSubmitted) {
            if (submittedIndicator) submittedIndicator.style.display = 'block';
            if (sideCardBtn) sideCardBtn.style.display = 'none';
        } else {
            if (submittedIndicator) submittedIndicator.style.display = 'none';
            if (sideCardBtn) sideCardBtn.style.display = '';
        }
    }

    function checkToastClosed() {
        return sessionStorage.getItem(SESSION_KEY) === '1' || toastClosed;
    }

    function showToast() {
        if (!toast || isSubmitted() || checkToastClosed()) return;
        toast.classList.add('show');
    }

    function hideToast() {
        if (!toast) return;
        toast.classList.remove('show');
        toastClosed = true;
        sessionStorage.setItem(SESSION_KEY, '1');
    }

    function openModal() {
        if (!modalOverlay) return;
        hideToast();
        modalOverlay.style.display = 'flex';
    }

    function closeModal() {
        if (!modalOverlay) return;
        modalOverlay.style.display = 'none';
    }

    // ---- 初始化：先同步服务端状态，再渲染 UI ----
    async function syncSubmissionStatus() {
        try {
            const resp = await fetch('/resume/check');
            const data = await resp.json();
            if (data.submitted) {
                _isSubmitted = true;
                localStorage.setItem(STORAGE_KEY, '1');
            } else {
                _isSubmitted = false;
                localStorage.removeItem(STORAGE_KEY);
            }
        } catch (err) {
            // 网络异常时，回退到 localStorage（离线容错）
            _isSubmitted = localStorage.getItem(STORAGE_KEY) === '1';
        }
        _serverChecked = true;
        updateResumeUI();

        // 同步完成后，再启动 Toast 计时
        if (toast && !isSubmitted() && !checkToastClosed()) {
            toastTimer = setTimeout(showToast, TOAST_DELAY);
        }
    }

    // 立即发起同步（不阻塞页面渲染）
    syncSubmissionStatus();

    // ---- 事件绑定 ----
    if (dismissBtn) dismissBtn.addEventListener('click', hideToast);
    if (toastActionBtn) toastActionBtn.addEventListener('click', openModal);
    if (openBtn) openBtn.addEventListener('click', openModal);
    if (closeBtn) closeBtn.addEventListener('click', closeModal);

    // 点击遮罩关闭
    if (modalOverlay) {
        modalOverlay.addEventListener('click', function(e) {
            if (e.target === modalOverlay) closeModal();
        });
    }

    // Escape 关闭
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeModal();
    });

    // 表单提交
    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(this);

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 提交中...';
            }

            try {
                const resp = await fetch('/resume/upload', { method: 'POST', body: formData });
                const data = await resp.json();
                if (resultDiv) {
                    resultDiv.style.display = 'block';
                    if (data.success) {
                        resultDiv.innerHTML = `<div class="alert alert-success py-2" style="font-size:0.85rem;border-radius:10px;">✓ ${data.message}</div>`;
                        markSubmitted();
                        // 跳转到「我的简历」追踪页面
                        setTimeout(() => { window.location.href = '/my-resumes'; }, 1500);
                    } else {
                        resultDiv.innerHTML = `<div class="alert alert-danger py-2" style="font-size:0.85rem;border-radius:10px;">✗ ${data.message}</div>`;
                    }
                }
            } catch (err) {
                if (resultDiv) {
                    resultDiv.style.display = 'block';
                    resultDiv.innerHTML = '<div class="alert alert-danger py-2" style="font-size:0.85rem;border-radius:10px;">网络错误，请重试</div>';
                }
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="bi bi-send"></i> 提交简历';
                }
            }
        });
    }

    console.log('[Resume Popup] Ready');
})();
