"""
Hong Kong API Proxy — Stateless microservice for Hunyuan 3D API.

Deploy on Alibaba Cloud HK lightweight server.
Routes submit/query calls to Tencent Cloud via low-latency HK→China path.

Protected by shared secret (X-Proxy-Secret header).
"""

import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ── Config (all from env) ───────────────────────────────────────────────────
HUNYUAN_ENDPOINT = os.getenv("HUNYUAN_ENDPOINT", "https://api.ai3d.cloud.tencent.com")
HUNYUAN_API_KEY  = os.getenv("HUNYUAN_API_KEY", "")
PROXY_SECRET     = os.getenv("PROXY_SECRET", "")

SUBMIT_URL = f"{HUNYUAN_ENDPOINT}/v1/ai3d/submit"
QUERY_URL  = f"{HUNYUAN_ENDPOINT}/v1/ai3d/query"

HEADERS_TEMPLATE = {
    "Authorization": HUNYUAN_API_KEY,
    "Content-Type":  "application/json",
}

# ── Auth guard ──────────────────────────────────────────────────────────────
def _check_secret():
    if PROXY_SECRET:
        return request.headers.get("X-Proxy-Secret", "") == PROXY_SECRET
    return True


# ── Routes ──────────────────────────────────────────────────────────────────
@app.route("/proxy/submit", methods=["POST"])
def proxy_submit():
    if not _check_secret():
        return jsonify({"error": "unauthorized"}), 403
    try:
        resp = requests.post(SUBMIT_URL, headers=HEADERS_TEMPLATE,
                             json=request.get_json(), timeout=30)
        return resp.content, resp.status_code, {"Content-Type": "application/json"}
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502


@app.route("/proxy/query", methods=["POST"])
def proxy_query():
    if not _check_secret():
        return jsonify({"error": "unauthorized"}), 403
    try:
        resp = requests.post(QUERY_URL, headers=HEADERS_TEMPLATE,
                             json=request.get_json(), timeout=30)
        return resp.content, resp.status_code, {"Content-Type": "application/json"}
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
