import sys
c = open('templates/messages.html', encoding='utf-8').read()

# Add the script section before </body>
script_js = r'''
<script>
    let msgs = [];
    let pendingImagePath = '';

    async function loadMsgs() {
        try {
            const res = await fetch('/api/messages');
            const data = await res.json();
            if (!data.ok) return;
            msgs = data.messages;
            renderMsgs();
        } catch(e) {}
    }

    function renderMsgs() {
        const el = document.getElementById('chatMessages');
        if (!msgs.length) {
            el.innerHTML = '<div class="empty-chat">No messages yet. Send us a message!</div>';
            return;
        }
        const wasAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        el.innerHTML = msgs.map(m => {
            const hasImage = m.image_path && m.image_path.trim() !== '';
            const senderClass = m.sender === 'customer' ? 'customer' :
                               (m.sender === 'system' ? 'system' : 'admin');
            const avatar = m.sender === 'customer' ? 'Y' : 'M';
            const content = (m.content || '').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
            const imgHtml = hasImage
                ? '<img class="msg-img" src="' + (m.image_path || '').replace(/"/g, '&quot;') + '" onclick="event.stopPropagation();openLightbox(\'' + (m.image_path || '').replace(/"/g, '&quot;') + '\')" loading="lazy">'
                : '';
            return '<div class="msg-row ' + senderClass + '">' +
                '<div class="msg-avatar">' + avatar + '</div>' +
                '<div class="msg-bubble">' +
                '<div>' + content + imgHtml + '</div>' +
                '<div class="msg-time">' + fmtTime(m.created_at) + '</div>' +
                '</div></div>';
        }).join('');
        if (wasAtBottom) el.scrollTop = el.scrollHeight;
    }

    async function sendMsg() {
        const input = document.getElementById('msgInput');
        const content = input.value.trim();
        if (!content && !pendingImagePath) return;

        let body;
        let headers = {};
        if (pendingImagePath) {
            headers['Content-Type'] = 'application/json';
            body = JSON.stringify({ content: content, image_path: pendingImagePath });
        } else {
            headers['Content-Type'] = 'application/json';
            body = JSON.stringify({ content: content });
        }

        const res = await fetch('/api/messages', {
            method: 'POST',
            headers: headers,
            body: body
        });
        const data = await res.json();
        if (data.ok) {
            input.value = '';
            removeImage();
            await loadMsgs();
            const el = document.getElementById('chatMessages');
            el.scrollTop = el.scrollHeight;
        }
    }

    async function handleImageUpload(input) {
        if (!input.files.length) return;
        const file = input.files[0];
        if (file.size > 10 * 1024 * 1024) {
            alert('Image too large. Maximum 10MB.');
            input.value = '';
            return;
        }
        const formData = new FormData();
        formData.append('image', file);
        try {
            const res = await fetch('/api/upload-chat-image', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.ok) {
                pendingImagePath = data.image_path;
                document.getElementById('imagePreviewImg').src = data.url;
                document.getElementById('imagePreviewWrap').style.display = 'inline-block';
            }
        } catch(e) {}
        input.value = '';
    }

    function removeImage() {
        pendingImagePath = '';
        document.getElementById('imagePreviewWrap').style.display = 'none';
    }

    function openLightbox(src) {
        document.getElementById('lightboxImg').src = src;
        document.getElementById('lightbox').classList.add('show');
    }
    function closeLightbox() {
        document.getElementById('lightbox').classList.remove('show');
    }

    function fmtTime(ts) {
        if (!ts) return '';
        const d = new Date(ts + 'Z');
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function escapeHtml(s) {
        const div = document.createElement('div');
        div.textContent = s || '';
        return div.innerHTML;
    }

    function escapeAttr(s) {
        return (s || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    // Quick replies
    fetch('/api/quick-replies')
        .then(r => r.json())
        .then(data => {
            if (data.ok && data.replies) {
                const qr = document.getElementById('quickReplies');
                data.replies.forEach(reply => {
                    const btn = document.createElement('button');
                    btn.className = 'quick-reply-btn';
                    btn.textContent = reply;
                    btn.onclick = () => {
                        document.getElementById('msgInput').value = reply;
                        document.getElementById('msgInput').focus();
                    };
                    qr.appendChild(btn);
                });
            }
        });

    loadMsgs();
    setInterval(loadMsgs, 3000);

    // Auto-resize textarea
    document.getElementById('msgInput').addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 150) + 'px';
    });

    // Show 'Back to Preview' if navigated from generate with task_id
    (function() {
        const params = new URLSearchParams(window.location.search);
        const tid = params.get('task_id');
        if (tid) {
            const btn = document.getElementById('backToPreview');
            btn.href = '/generate?task_id=' + tid;
            btn.style.display = 'inline-block';
        }
    })();

    // My Models Sidebar
    async function loadMyModels() {
        try {
            const res = await fetch('/api/my-models');
            const data = await res.json();
            if (!data.ok) return;
            const list = document.getElementById('modelList');
            const badge = document.getElementById('modelBadge');
            const models = data.models || [];
            badge.textContent = models.length;
            if (models.length === 0) {
                list.innerHTML = '<div class="sidebar-empty">\u6682\u65e0\u6a21\u578b\uff0c\u5feb\u53bb\u751f\u6210\u5427</div>';
                return;
            }
            list.innerHTML = models.map(m => {
                const statusMap = {
                    pending: 'generating',
                    processing: 'generating',
                    queued: 'generating',
                    in_progress: 'generating',
                    completed: 'completed',
                    failed: 'failed'
                };
                const statusLabels = {
                    pending: '\u751f\u6210\u4e2d',
                    processing: '\u751f\u6210\u4e2d',
                    queued: '\u6392\u961f\u4e2d',
                    in_progress: '\u751f\u6210\u4e2d',
                    completed: '\u5df2\u5b8c\u6210',
                    failed: '\u5931\u8d25'
                };
                const st = statusMap[m.status] || 'generating';
                const label = statusLabels[m.status] || m.status;
                const tid = m.task_id || '';
                const shortId = tid.length > 8 ? tid.substring(0, 8) + '...' : tid;
                const thumbHtml = m.thumbnail_url
                    ? '<img src="' + escapeAttr(m.thumbnail_url) + '" alt="" onerror="this.parentElement.innerHTML=\\'<span class=\\'no-thumb\\'>\\ud83d\\udce6</span>\\'">'
                    : '<span class="no-thumb">\\ud83d\\udce6</span>';
                const timeHtml = m.completed_at
                    ? new Date(m.completed_at + 'Z').toLocaleDateString()
                    : '';
                const promptText = m.prompt ? escapeHtml(m.prompt) : shortId;
                return '<a class="model-item" href="/result/' + encodeURIComponent(tid) + '">' +
                    '<div class="model-thumb">' + thumbHtml + '</div>' +
                    '<div class="model-info">' +
                    '<div class="model-id">#' + escapeHtml(shortId) + '</div>' +
                    '<div class="model-prompt">' + promptText + '</div>' +
                    '<div class="model-meta">' +
                    '<span class="model-status-tag ' + st + '">' + label + '</span>' +
                    (timeHtml ? '<span>' + timeHtml + '</span>' : '') +
                    '</div></div></a>';
            }).join('');
        } catch(e) {
            console.error('Failed to load models:', e);
        }
    }

    function toggleSidebar() {
        const sb = document.getElementById('modelsSidebar');
        sb.classList.toggle('open');
    }

    document.addEventListener('click', function(e) {
        const sb = document.getElementById('modelsSidebar');
        if (sb && sb.classList.contains('open')) {
            if (!sb.contains(e.target) && e.target.id !== 'sidebarToggle') {
                sb.classList.remove('open');
            }
        }
    });

    loadMyModels();
</script>
'''

c = c.replace('</body>', script_js + '\n</body>')

with open('templates/messages.html', 'w', encoding='utf-8') as f:
    f.write(c)
print('Script added. Size:', len(c))
