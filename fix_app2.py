import sys, re
c = open('app.py', encoding='utf-8').read()
pattern = r'def api_my_models\(\).*?(?=\n@app\.route|\Z)'
match = re.search(pattern, c, re.DOTALL)

new = """def api_my_models():
    if not is_logged_in():
        return jsonify({"ok": False, "error": "Not logged in"}), 401

    cid = session.get("customer_id")
    with get_db() as conn:
        rows = conn.execute(
            "SELECT job_id AS task_id, status, input_text AS prompt, "
            "preview_image_url AS thumbnail_url, completed_at "
            "FROM generation_tasks WHERE customer_id=? "
            "ORDER BY created_at DESC",
            (cid,),
        ).fetchall()

    models = []
    for r in rows:
        d = dict(r)
        if d["prompt"] and len(d["prompt"]) > 30:
            d["prompt"] = d["prompt"][:30]
        models.append(d)

    return jsonify({"ok": True, "models": models})
"""

c = c[:match.start()] + new + c[match.end():]
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(c)
print('Fixed')
