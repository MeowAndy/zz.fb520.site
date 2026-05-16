#!/usr/bin/env python3
"""Sponsor list API for zz.fb520.site"""
import json
import os
import uuid
from functools import wraps
from flask import Flask, request, jsonify

app = Flask(__name__)

DATA_DIR = "/opt/1panel/www/sites/zz.fb520.site/index/data"
DATA_FILE = os.path.join(DATA_DIR, "sponsors.json")
ADMIN_PASSWORD = os.environ.get("SPONSOR_ADMIN_PWD", "changeme")


def load_sponsors():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_sponsors(sponsors):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(sponsors, f, ensure_ascii=False, indent=2)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        password = request.headers.get("X-Admin-Password") or request.json.get("password", "")
        if password != ADMIN_PASSWORD:
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/api/sponsors", methods=["GET"])
def get_sponsors():
    sponsors = load_sponsors()
    return jsonify(sponsors)


@app.route("/api/sponsors", methods=["POST"])
@require_auth
def add_sponsor():
    data = request.json
    name = data.get("name", "").strip()
    amount = data.get("amount", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    sponsor = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "amount": amount,
        "date": data.get("date", "")
    }
    sponsors = load_sponsors()
    sponsors.insert(0, sponsor)
    save_sponsors(sponsors)
    return jsonify(sponsor), 201


@app.route("/api/sponsors/<sponsor_id>", methods=["DELETE"])
@require_auth
def delete_sponsor(sponsor_id):
    sponsors = load_sponsors()
    sponsors = [s for s in sponsors if s["id"] != sponsor_id]
    save_sponsors(sponsors)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5100)
