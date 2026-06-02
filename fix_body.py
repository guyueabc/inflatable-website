import sys
c = open('templates/messages.html', encoding='utf-8').read()
body_start = c.find('<body>') + 6
body_end = c.rfind('</body>')

new_body = '''

<header class="navbar">
    <a href="/" class="logo">Inflatable<span>Model</span>.CN</a>
    <button class="sidebar-toggle" id="sidebarToggle" onclick="toggleSidebar()">&amp;#9776;</button>
    <div class="nav-links">
        <a href="/">Home</a>
        <a href="/generate">Create 3D</a>
        <a href="/messages" class="active">Messages <span id="notifBadge" style="display:none;background:#ef4444;color:#fff;border-radius:50%;padding:1px 6px;font-size:.625rem;margin-left:4px;vertical-align:top;">0</span></a>
    </div>
</header>

<div class="page-layout">
    <div class="models-sidebar" id="modelsSidebar">
        <div class="sidebar-header">
            \u6211\u7684\u6a21\u578b
            <span class="badge" id="modelBadge">0</span>
        </div>
        <div class="model-list" id="modelList"></div>
    </div>

    <div class="chat-wrapper">
        <div class="chat-header">
            <div class="chat-avatar">M</div>
            <div class="chat-header-info">
                <h2>Mia — Your Consultant</h2>
                <span>Online · InflatableModel.CN</span>
            </div>
            <a id="backToPreview" href="/generate" style="display:none;margin-left:auto;padding:6px 12px;border-radius:8px;border:1px solid var(--border);color:var(--text-secondary);font-size:.8125rem;text-decoration:none;white-space:nowrap;transition:.2s;">
                &larr; Back to Preview
            </a>
        </div>

        <div class="chat-messages" id="chatMessages">
            <div class="empty-chat">No messages yet. Send us a message!</div>
        </div>

        <div class="chat-input-area">
            <div class="image-preview-row" id="imagePreviewWrap" style="display:none;">
                <img id="imagePreviewImg" src="" alt="Preview">
                <button class="remove-preview" onclick="removeImage()">&amp;times;</button>
            </div>
            <div class="quick-replies" id="quickReplies"></div>
            <div class="input-row">
                <button class="attach-btn" onclick="document.getElementById('imageInput').click()" title="Attach image">&amp;#128206;</button>
                <textarea id="msgInput" placeholder="Type your message..." rows="1"></textarea>
                <button class="send-btn" onclick="sendMsg()">Send</button>
            </div>
            <input type="file" id="imageInput" accept="image/*" style="display:none" onchange="handleImageUpload(this)">
        </div>
    </div>
</div>

<!-- Lightbox -->
<div class="lightbox" id="lightbox" onclick="closeLightbox()">
    <button class="lightbox-close">&amp;times;</button>
    <img id="lightboxImg" src="" alt="">
</div>

'''

c = c[:body_start] + new_body + c[body_end:]

with open('templates/messages.html', 'w', encoding='utf-8') as f:
    f.write(c)
print('Body replaced. Size:', len(c))
