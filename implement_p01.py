# Step 1: P0-1 - Add "my models" API to app.py
c = open("app.py", encoding="utf-8").read()

# Add the /api/my-models endpoint - find a good spot after the /api/me route
api_me_idx = c.find("def api_me")
if api_me_idx > 0:
    # Find the end of the api_me function
    end_idx = c.find("\n@app.route", api_me_idx + 100)
    
    my_models_code = """

@app.route("/api/my-models")
def api_my_models():
    \"\"\"Return the current user\'s generation tasks.\"\"\"
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Not logged in"})
    try:
        cur = get_db().execute(\"\"\"
            SELECT task_id, status, prompt, image_path, thumbnail_url, 
                   created_at, completed_at 
            FROM generation_tasks 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 50
        \"\"\", (user_id,))
        tasks = [{
            "task_id": row["task_id"],
            "status": row["status"],
            "prompt": (row["prompt"] or "")[:60],
            "image_path": row["image_path"],
            "thumbnail_url": row["thumbnail_url"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"]
        } for row in cur.fetchall()]
        return jsonify({"ok": True, "tasks": tasks})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

"""
    c = c[:end_idx] + my_models_code + c[end_idx:]
    open("app.py", "w", encoding="utf-8").write(c)
    print("P0-1: Added /api/my-models endpoint")
else:
    print("Could not find api_me")
