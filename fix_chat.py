import sys
with open("backup_20260602_final/admin_chat.py", "r", encoding="utf-8-sig") as f:
    content = f.read()

old_body = "    data = request.get_json(force=True, silent=True) or {}\n    customer_id = (data.get(\"customer_id\") or \"\").strip()\n    content = (data.get(\"content\") or \"\").strip()\n    image_path = (data.get(\"image_path\") or \"\").strip()"

new_body = "    # Support both JSON and multipart/form-data\n    if request.is_json:\n        data = request.get_json(force=True, silent=True) or {}\n        customer_id = (data.get(\"customer_id\") or \"\").strip()\n        content = (data.get(\"content\") or \"\").strip()\n        image_path = (data.get(\"image_path\") or \"\").strip()\n    else:\n        customer_id = (request.form.get(\"customer_id\") or \"\").strip()\n        content = (request.form.get(\"content\") or \"\").strip()\n        image_path = (request.form.get(\"image_path\") or \"\").strip()"

idx = content.find("def api_admin_reply")
if idx > 0:
    funcStart = content.find(old_body, idx)
    if funcStart > 0:
        content = content[:funcStart] + new_body + content[funcStart + len(old_body):]
        with open("admin_chat.py", "w", encoding="utf-8") as f:
            f.write(content)
        print("Done - Fixed api_admin_reply")
    else:
        print("ERROR: old_body not found in function")
else:
    print("ERROR: api_admin_reply not found")
