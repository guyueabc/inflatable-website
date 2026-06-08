"""Step 1: Import config and mailer"""
import sys
print("Step 1: Importing config...", file=sys.stderr)
import config
print("Step 1 OK", file=sys.stderr)

print("Step 2: Importing mailer...", file=sys.stderr)
import mailer
print("Step 2 OK", file=sys.stderr)

print("Step 3: Creating Flask app...", file=sys.stderr)
from flask import Flask, render_template
app = Flask(__name__)
app.config.from_object(config)
print("Step 3 OK", file=sys.stderr)

print("Step 4: Importing flask_session...", file=sys.stderr)
from flask_session import Session
Session(app)
print("Step 4 OK", file=sys.stderr)

print("Step 5: Importing admin_chat...", file=sys.stderr)
from admin_chat import chat_bp
print("Step 5 OK", file=sys.stderr)

print("Step 6: Importing admin_traffic...", file=sys.stderr)
from admin_traffic import traffic_bp
print("Step 6 OK", file=sys.stderr)

print("Step 7: Registering blueprints...", file=sys.stderr)
app.register_blueprint(chat_bp)
app.register_blueprint(traffic_bp)
print("Step 7 OK", file=sys.stderr)

print("ALL STEPS PASSED - Starting server", file=sys.stderr)

@app.route("/")
def home():
    return "<h1>Shein Eyelash is LIVE!</h1><p>All imports OK!</p>"

import os
port = int(os.getenv("PORT", 10000))
app.run(host="0.0.0.0", port=port)
