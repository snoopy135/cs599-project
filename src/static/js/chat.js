/**
 * AI 问答聊天 — 前端交互逻辑
 */
(function() {
    'use strict';

    const chatMessages = document.getElementById('chatMessages');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const clearBtn = document.getElementById('clearChatBtn');
    const welcomeArea = document.getElementById('welcomeArea');
    const modeBadge = document.getElementById('modeBadge');
    let isProcessing = false;

    if (!chatInput || !sendBtn) return;

    function addMessage(role, content, sources) {
        if (welcomeArea) welcomeArea.style.display = 'none';

        const div = document.createElement('div');
        div.className = `chat-message ${role}`;

        let formatted = content
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/### (.+)/g, '<strong>$1</strong>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');

        let sourceTags = '';
        if (sources && sources.length > 0) {
            sourceTags = '<div style="margin-top:10px;">';
            const seen = new Set();
            for (const s of sources) {
                if (!seen.has(s.title)) {
                    seen.add(s.title);
                    sourceTags += `<span class="source-tag">📄 ${s.title}</span>`;
                }
            }
            sourceTags += '</div>';
        }

        div.innerHTML = `
            <div class="message-wrapper">
                <div class="message-content"><p>${formatted}</p>${sourceTags}</div>
                <div class="message-meta">${role === 'user' ? '我' : '🤖 AI 助手'} · ${new Date().toLocaleTimeString()}</div>
            </div>
        `;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    function showTyping() {
        const div = document.createElement('div');
        div.className = 'chat-message assistant';
        div.id = 'typingIndicator';
        div.innerHTML = `
            <div class="message-wrapper">
                <div class="message-content" style="padding:16px 20px;">
                    <div style="display:flex;gap:5px;">
                        <span style="width:7px;height:7px;border-radius:50%;background:#c4b5fd;animation:dotPulse 1.4s infinite;"></span>
                        <span style="width:7px;height:7px;border-radius:50%;background:#a78bfa;animation:dotPulse 1.4s 0.2s infinite;"></span>
                        <span style="width:7px;height:7px;border-radius:50%;background:#8b7cf0;animation:dotPulse 1.4s 0.4s infinite;"></span>
                    </div>
                </div>
            </div>
        `;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    function removeTyping() {
        const el = document.getElementById('typingIndicator');
        if (el) el.remove();
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function sendMessage(message) {
        if (isProcessing || !message || !message.trim()) return;

        isProcessing = true;
        sendBtn.disabled = true;
        chatInput.disabled = true;

        addMessage('user', message.trim());
        chatInput.value = '';
        showTyping();

        try {
            const resp = await fetch('/chat/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message.trim() })
            });
            const data = await resp.json();
            removeTyping();

            if (data.success) {
                addMessage('assistant', data.answer, data.sources);
                if (modeBadge) {
                    if (data.fallback_mode) {
                        modeBadge.textContent = '检索模式';
                        modeBadge.className = 'badge-mode fallback';
                    } else {
                        modeBadge.textContent = 'AI 增强模式';
                        modeBadge.className = 'badge-mode ai';
                    }
                }
            } else {
                addMessage('assistant', '抱歉，处理时出错了：' + (data.message || '请稍后重试'));
            }
        } catch (err) {
            removeTyping();
            addMessage('assistant', '网络请求失败，请检查网络后重试。');
        } finally {
            isProcessing = false;
            sendBtn.disabled = false;
            chatInput.disabled = false;
            chatInput.focus();
        }
    }

    sendBtn.addEventListener('click', () => sendMessage(chatInput.value));
    chatInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(chatInput.value);
        }
    });

    if (clearBtn) {
        clearBtn.addEventListener('click', async () => {
            if (isProcessing || !confirm('确定开始新对话？')) return;
            try {
                await fetch('/chat/clear', { method: 'POST' });
                chatMessages.innerHTML = '';
                if (welcomeArea) welcomeArea.style.display = '';
                if (modeBadge) { modeBadge.textContent = 'AI 增强模式'; modeBadge.className = 'badge-mode ai'; }
            } catch (e) { /* ignore */ }
        });
    }

    // 快捷问题点击
    document.querySelectorAll('.quick-question-tag').forEach(tag => {
        tag.addEventListener('click', () => sendMessage(tag.dataset.question));
    });

    // 动画 keyframes
    if (!document.getElementById('dotPulseStyle')) {
        const style = document.createElement('style');
        style.id = 'dotPulseStyle';
        style.textContent = '@keyframes dotPulse{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-6px)}}';
        document.head.appendChild(style);
    }

    console.log('[Chat] Ready');
})();
