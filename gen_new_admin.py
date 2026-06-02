import os, re

DIR = "D:\\2\\inflatable-website\\templates"

# Read the original admin.html (the fully functional one with chat + traffic tabs)
with open(os.path.join(DIR, "admin.html"), "r", encoding="utf-8") as f:
    base = f.read()

# Read the traffic.html to extract the traffic section  
with open(os.path.join(DIR, "admin_traffic.html"), "r", encoding="utf-8") as f:
    traffic_html = f.read()

# =====================================================================
# Strategy: Take admin.html, replace its top with horizontal nav,
# merge traffic section into right panel tab, keep everything else
# =====================================================================

# 1. Replace the app-layout structure
old_layout_start = base.find('<div class="app-layout">')
old_layout_end = base.find("</div>", base.find('id="panelRight"'))
# Find the matching closing div
depth = 0
cut_end = old_layout_start
for i in range(old_layout_start, len(base)):
    c = base[i]
    if c == "<":
        if base[i:i+6] == "</div>":
            depth -= 1
            if depth < 0:
                cut_end = i + 6
                break
    elif c == "<" and base[i:i+5] == "<div ":
        depth += 1

# Get the old body content
old_body = base[old_layout_start:cut_end]

# 2. Extract the traffic section CSS and content from traffic page
# Get traffic chart CSS  
traffic_css_match = re.search(r'/\* Traffic Charts \*/(.*?)(?=\})', traffic_html, re.DOTALL)
traffic_additional_css = ""
if traffic_css_match:
    traffic_additional_css = "        " + traffic_css_match.group(0) + "\n"

# Extract the traffic stats content  
traffic_section_start = traffic_html.find('id="trafficSection"')
traffic_section_end = traffic_html.find("</div>", traffic_html.find("id=\"chartMonthlyWrap\""))
# Go to the end of the right panel
for j in range(traffic_section_end, min(traffic_section_end + 200, len(traffic_html))):
    if traffic_html[j:j+6] == "</div>" and traffic_html[j-20:j].strip().endswith("</div>"):
        traffic_section_end = j + 6
        break

traffic_content = traffic_html[traffic_section_start-50:traffic_section_end]

# 3. Extract the traffic JS
traffic_js_start = traffic_html.find("function switchPeriod")
traffic_js_end = traffic_html.find("</script>", traffic_js_start) + 9
traffic_js = traffic_html[traffic_js_start:traffic_js_end]

# 4. Build the new body
new_body = '''<div class="app-layout">
    <!-- Top Navigation Bar -->
    <div class="top-nav">
        <a href="/" class="top-nav-brand">Inflatable<span>Model</span></a>
        <div class="top-nav-tabs" id="mainTabs">
            <button class="top-nav-tab active" onclick="switchMainTab('chat')" id="tabBtnChat">聊天管理</button>
            <button class="top-nav-tab" onclick="switchMainTab('traffic')" id="tabBtnTraffic">流量统计</button>
        </div>
        <div class="top-nav-right">
            <button class="top-nav-logout" onclick="fetch('/api/admin/logout',{method:'POST'}).then(()=>location.reload())">退出</button>
        </div>
    </div>

    <!-- Chat Panel (visible by default) -->
    <div id="tabChat" class="tab-content" style="display:flex;flex:1;height:calc(100vh - 48px);">
'''

# Remove the old header/nav from the chat body
chat_body = old_body
# Remove the old panel-left-header (it was replaced in admin_chat.html)
chat_body = re.sub(r'<div class="panel-left-header">.*?</div>', '', chat_body, flags=re.DOTALL)
# Remove search wrap
chat_body = re.sub(r'<div class="search-wrap">.*?</div>', '', chat_body, flags=re.DOTALL)

new_body += chat_body

new_body += '''
    </div>
    
    <!-- Traffic Panel (hidden by default) -->
    <div id="tabTraffic" class="tab-content" style="display:none;flex:1;height:calc(100vh - 48px);">
        <div style="padding:20px;overflow-y:auto;width:100%;">
'''

new_body += traffic_content

new_body += '''
        </div>
    </div>
</div>
'''

# 5. Build the complete page
# Take everything before app-layout from base
head_section = base[:old_layout_start]

# Add traffic chart CSS
head_section = head_section.replace("</style>", traffic_additional_css + "    </style>")

# Add nav CSS
nav_css = '''
        /* Top Navigation */
        .top-nav {
            position: fixed; top: 0; left: 0; right: 0; height: 48px;
            background: #1e293b; border-bottom: 1px solid #334155;
            display: flex; align-items: center; padding: 0 20px; z-index: 200;
        }
        .top-nav-brand { font-size: 1rem; font-weight: 800; color: #f1f5f9; text-decoration: none; margin-right: 32px; }
        .top-nav-brand span { color: #6366f1; }
        .top-nav-tabs { display: flex; gap: 4px; }
        .top-nav-tab {
            padding: 8px 20px; border: none; background: transparent; color: #94a3b8;
            border-radius: 6px; font-size: .85rem; font-weight: 500;
            cursor: pointer; font-family: inherit; transition: all .15s;
        }
        .top-nav-tab:hover { background: rgba(99,102,241,0.1); color: #6366f1; }
        .top-nav-tab.active { background: #6366f1; color: #fff; font-weight: 600; }
        .top-nav-right { margin-left: auto; }
        .top-nav-logout {
            padding: 6px 14px; border: 1px solid #334155; background: transparent;
            color: #94a3b8; border-radius: 6px; font-size: .8rem;
            cursor: pointer; font-family: inherit;
        }
        .top-nav-logout:hover { border-color: #ef4444; color: #ef4444; }
        .tab-content { margin-top: 0; }
'''
head_section = head_section.replace("</style>", nav_css + "    </style>")

# Take everything after the original app-layout's </html>
after_layout = base[cut_end:]

# Add chart.js script and traffic JS before </body>
chart_script = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>\n'
traffic_loader_js = '''
<script>
function switchMainTab(tab) {
    document.querySelectorAll(".top-nav-tab").forEach(b => {
        b.classList.toggle("active", b.id === "tabBtnChat" ? tab === "chat" : tab === "traffic");
    });
    document.getElementById("tabChat").style.display = tab === "chat" ? "flex" : "none";
    document.getElementById("tabTraffic").style.display = tab === "traffic" ? "block" : "none";
    if (tab === "traffic" && typeof loadTraffic === "function") {
        setTimeout(loadTraffic, 200);
    }
}
</script>
'''

# Insert chart.js and traffic_js into the after_layout
after_layout = after_layout.replace("</body>", chart_script + traffic_loader_js + traffic_js + "\n</body>")

# Remove duplicate chart.js (from admin_old)
after_layout = after_layout.replace(
    '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>',
    ""
)

# Remove old chart vars
after_layout = re.sub(r'let chartLineInst = null;\s*let chartPieInst = null;', '', after_layout)

# Assemble
full_page = head_section + new_body + after_layout

# Write
out_path = os.path.join(DIR, "admin.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(full_page)

print(f"Written {out_path}")
print(f"Size: {len(full_page)} chars")
print(f"switchMainTab present: {'switchMainTab' in full_page}")
print(f"tabChat present: {'tabChat' in full_page}")
print(f"tabTraffic present: {'tabTraffic' in full_page}")
print(f"loadTraffic present: {'loadTraffic' in full_page}")
print(f"chat label present: {'\u804a\u5929\u7ba1\u7406' in full_page}")
print(f"traffic label present: {'\u6d41\u91cf\u7edf\u8ba1' in full_page}")
