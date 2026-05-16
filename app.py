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
ADMIN_PASSWORD = "fzmandy123"


def load_sponsors():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_sponsors(sponsors):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(sponsors, f, ensure_ascii=False, indent=2)



def recalc_income():
    """Recalculate income from all sponsors - single source of truth."""
    sponsors = load_sponsors()
    total = 0
    for sp in sponsors:
        try:
            total += float(sp.get("amount","").replace("+","").replace("¥","").replace(",",""))
        except (ValueError, TypeError):
            pass
    fin = load_finance()
    fin["income"] = round(total, 2)
    save_finance(fin)
    return fin

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
    sponsors.append(sponsor)
    save_sponsors(sponsors)
    recalc_income()
    return jsonify(sponsor), 201



@app.route("/api/sponsors/<sponsor_id>", methods=["PUT"])
@require_auth
def update_sponsor(sponsor_id):
    data = request.json
    sponsors = load_sponsors()
    for s in sponsors:
        if s["id"] == sponsor_id:
            if "name" in data:
                s["name"] = data["name"].strip()
            if "amount" in data:
                s["amount"] = data["amount"].strip()
            break
    else:
        return jsonify({"error": "not found"}), 404
    save_sponsors(sponsors)
    recalc_income()
    return jsonify(s)

@app.route("/api/sponsors/<sponsor_id>", methods=["DELETE"])
@require_auth
def delete_sponsor(sponsor_id):
    sponsors = load_sponsors()
    sponsors = [s for s in sponsors if s["id"] != sponsor_id]
    save_sponsors(sponsors)
    recalc_income()
    return jsonify({"ok": True})




# --- Finance ---
FINANCE_FILE = os.path.join(DATA_DIR, "finance.json")

def load_finance():
    if not os.path.exists(FINANCE_FILE):
        return {"income": 0, "expense": 0}
    with open(FINANCE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_finance(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FINANCE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/api/finance", methods=["GET"])
def get_finance():
    fin = load_finance()
    income = float(fin.get("income", 0))
    expense = float(fin.get("expense", 0))
    balance = round(income - expense, 2)
    return jsonify({"income": income, "expense": expense, "balance": balance, "status": "盈利" if balance >= 0 else "亏损"})

@app.route("/api/finance", methods=["PUT"])
@require_auth
def update_finance():
    data = request.json
    fin = load_finance()
    if "income" in data:
        fin["income"] = float(data["income"])
    if "expense" in data:
        fin["expense"] = float(data["expense"])
    save_finance(fin)
    income = float(fin.get("income", 0))
    expense = float(fin.get("expense", 0))
    balance = round(income - expense, 2)
    return jsonify({"income": income, "expense": expense, "balance": balance, "status": "盈利" if balance >= 0 else "亏损"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5100)
