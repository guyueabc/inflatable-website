import sys
with open('templates/messages.html', encoding='utf-8') as f:
    c = f.read()

print('File size:', len(c))
print('Contains page-layout:', 'page-layout' in c)
print('Contains modelsSidebar:', 'modelsSidebar' in c)
print('Contains sidebar-toggle:', 'sidebar-toggle' in c)
print('Contains toggleSidebar:', 'toggleSidebar' in c)
print('Contains loadMyModels (our version):', 'modelList' in c and 'modelBadge' in c)
