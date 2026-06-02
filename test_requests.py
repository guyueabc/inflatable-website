import requests
s = requests.Session()
r = s.get("http://localhost:5002/")
print("1. Homepage:", r.status_code, "cookies:", dict(s.cookies))
r = s.post("http://localhost:5002/api/login", json={"email": "ltj807133914@gmail.com"})
d = r.json()
print("2. Login:", d["ok"], "cookies:", dict(s.cookies))
r = s.get("http://localhost:5002/messages")
print("3. Messages:", r.status_code, "len:", len(r.text), "hasChat:", "chat-messages" in r.text)
r = s.post("http://localhost:5002/api/messages", json={"content": "REQUESTS_TEST"})
d = r.json()
print("4. Send:", d["ok"])
r = s.post("http://localhost:5002/api/upload-chat-image", files={"image": ("t.png", b"data", "image/png")})
d = r.json()
print("5. Upload:", d["ok"], d.get("image_path",""))
if d["ok"]:
    r = s.post("http://localhost:5002/api/messages", json={"content": "With image!", "image_path": d["image_path"]})
    print("6. Send w/img:", r.json()["ok"])
r = s.get("http://localhost:5002/api/messages")
msgs = r.json()["messages"]
last = msgs[-1]
print("7. Last: [" + last["sender"] + "] " + last["content"] + " img=" + str(last["image_path"] != ""))
print("ALL PASSED!")
