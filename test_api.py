import requests, json

base = "http://localhost:5002"

# 1. Test dev mode login (no email needed)
print("=== 1. Login (dev mode) ===")
r = requests.post(f"{base}/api/login", json={"email": "test@test.com"})
print(f"Status: {r.status_code}, Body: {r.json()}")
cookies = r.cookies

# 2. Send a message as customer
print("\n=== 2. Send customer message ===")
r = requests.post(f"{base}/api/messages", json={"content": "Hello from test!"}, cookies=cookies)
print(f"Status: {r.status_code}, Body: {r.json()}")

# 3. Get messages
print("\n=== 3. Get messages ===")
r = requests.get(f"{base}/api/messages", cookies=cookies)
data = r.json()
if data.get("ok"):
    print(f"Messages count: {len(data.get('messages', []))}")
    if data["messages"]:
        print(f"Last message: {data['messages'][-1]}")
else:
    print(f"Error: {data}")

# 4. Admin login
print("\n=== 4. Admin login ===")
r = requests.post(f"{base}/api/admin/login", json={"password": "admin123"})
print(f"Status: {r.status_code}, Body: {r.json()}")
admin_cookies = r.cookies

# 5. Admin get customers
print("\n=== 5. Admin get customers ===")
r = requests.get(f"{base}/api/admin/customers", cookies=admin_cookies)
data = r.json()
print(f"Status: {r.status_code}, Customers: {len(data.get('customers', []))}")
if data.get("customers"):
    first = data["customers"][0]
    print(f"First customer: id={first.get('id')}, name={first.get('name')}, unread={first.get('unread')}")
    cid = first["id"]
    
    # 6. Admin reply - send as FormData (mimicking browser)
    print(f"\n=== 6. Admin reply to {cid} ===")
    r = requests.post(f"{base}/api/admin/reply", data={"customer_id": cid, "content": "Hello! This is admin reply!"}, cookies=admin_cookies)
    print(f"Status: {r.status_code}, Body: {r.json()}")

    # 7. Admin get messages for this customer
    print(f"\n=== 7. Admin get messages for {cid} ===")
    r = requests.get(f"{base}/api/admin/messages/{cid}", cookies=admin_cookies)
    data = r.json()
    print(f"Status: {r.status_code}, Messages: {len(data.get('messages', []))}")
    for m in data.get("messages", [])[-3:]:
        print(f"  [{m['sender']}] {m['content'][:50]}")

# 8. Traffic summary
print("\n=== 8. Traffic summary ===")
r = requests.get(f"{base}/api/admin/traffic/summary?period=week", cookies=admin_cookies)
data = r.json()
print(f"Status: {r.status_code}")
if data.get("ok") != False:
    print(f"  PV: {data.get('pv')}, UV: {data.get('uv')}")
else:
    print(f"  Error: {data.get('error')}")

print("\n=== ALL TESTS COMPLETE ===")
