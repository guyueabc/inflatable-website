import re, os
chat = open('templates/admin_chat.html', encoding='utf-8').read()
traffic = open('templates/admin_traffic.html', encoding='utf-8').read()
print(f'chat={len(chat)}, traffic={len(traffic)}')
