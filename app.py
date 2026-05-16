#!/usr/bin/env python3
"""Sponsor list API for zz.fb520.site - v2 (no hardcoded passwords)"""
import json
import os
import uuid
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)

DATA_DIR = "/opt/1panel/www/sites/zz.fb520.site/index/data"
ASSETS_DIR = "/opt/1panel/www/sites/zz.fb520.site/index/assets"
DATA_FILE = os.path.join(DATA_DIR, "sponsors.json")
FINANCE_FILE = os.path.join(DATA_DIR, "finance.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB


# --- Config helpers ---
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# --- Sponsor helpers ---
def load_sponsors():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_sponsors(sponsors):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(sponsors, f, ensure_ascii=False, indent=2)


# --- Finance helpers ---
def load_finance():
    if not os.path.exists(FINANCE_FILE):
        return {"income": 0, "expense": 0}
    with open(FINANCE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_finance(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FINANCE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def recalc_income():
    """Recalculate income from all sponsors - single source of truth."""
    sponsors = load_sponsors()
    total = 0
    for sp in sponsors:
        try:
            total += float(sp.get("amount", "").replace("+", "").replace("¥", "").replace(",", ""))
        except (ValueError, TypeError):
            pass
    fin = load_finance()
    fin["income"] = round(total, 2)
    save_finance(fin)
    return fin


# --- Auth ---
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        cfg = load_config()
        password_hash = cfg.get("password_hash", "")
        if not password_hash:
            return jsonify({"error": "password not set"}), 403

        password = request.headers.get("X-Admin-Password", "")
        if not password and request.is_json:
            password = request.json.get("password", "")

        if not password or not check_password_hash(password_hash, password):
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Password management ---
@app.route("/api/password/status", methods=["GET"])
def password_status():
    cfg = load_config()
    has_password = bool(cfg.get("password_hash", ""))
    return jsonify({"has_password": has_password})


@app.route("/api/password/setup", methods=["POST"])
def setup_password():
    """Set password for the first time (only works if no password is set)."""
    cfg = load_config()
    if cfg.get("password_hash", ""):
        return jsonify({"error": "password already set, use change endpoint"}), 400
    data = request.json
    new_password = data.get("password", "").strip()
    if len(new_password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400
    cfg["password_hash"] = generate_password_hash(new_password)
    save_config(cfg)
    return jsonify({"ok": True, "message": "password set successfully"})


@app.route("/api/password/change", methods=["POST"])
@require_auth
def change_password():
    """Change password (requires current password in X-Admin-Password header)."""
    data = request.json
    new_password = data.get("new_password", "").strip()
    if len(new_password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400
    cfg = load_config()
    cfg["password_hash"] = generate_password_hash(new_password)
    save_config(cfg)
    return jsonify({"ok": True, "message": "password changed successfully"})


# --- Site config (title, subtitle, description, avatar, background) ---
@app.route("/api/config", methods=["GET"])
def get_site_config():
    cfg = load_config()
    site = cfg.get("site", {})
    return jsonify({
        "title": site.get("title", "赞助菲比 Bot"),
        "subtitle": site.get("subtitle", "鸣潮免费分享机器人 · 公益运行"),
        "description": site.get("description", "菲比 Bot 一直坚持免费公益运行，如果你觉得菲比帮到了你，可以请菲比喝杯奶茶 ☕ 感谢每一位支持者的温暖~"),
        "avatar": site.get("avatar", "assets/phoebe-avatar.jpg"),
        "background": site.get("background", "assets/bg-phoebe.jpg"),
        "footer": site.get("footer", "菲比 Bot · 鸣潮免费分享机器人 · 感谢你的支持 💛")
    })


@app.route("/api/config", methods=["PUT"])
@require_auth
def update_site_config():
    data = request.json
    cfg = load_config()
    site = cfg.get("site", {})
    for key in ["title", "subtitle", "description", "avatar", "background", "footer"]:
        if key in data:
            site[key] = data[key].strip()
    cfg["site"] = site
    save_config(cfg)
    return jsonify({"ok": True, "site": site})


# --- QR code upload ---
@app.route("/api/upload/qr/<qr_type>", methods=["POST"])
@require_auth
def upload_qr(qr_type):
    if qr_type not in ("wechat", "alipay", "qq"):
        return jsonify({"error": "invalid qr type, must be wechat/alipay/qq"}), 400

    if "file" not in request.files:
        return jsonify({"error": "no file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "no file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "file type not allowed"}), 400

    # Read and check size
    file_data = file.read()
    if len(file_data) > MAX_UPLOAD_SIZE:
        return jsonify({"error": "file too large (max 5MB)"}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{qr_type}.{ext}"
    filepath = os.path.join(ASSETS_DIR, filename)

    # Remove old file if extension differs
    for old_ext in ALLOWED_EXTENSIONS:
        old_path = os.path.join(ASSETS_DIR, f"{qr_type}.{old_ext}")
        if old_path != filepath and os.path.exists(old_path):
            os.remove(old_path)

    with open(filepath, "wb") as f:
        f.write(file_data)

    return jsonify({"ok": True, "path": f"assets/{filename}"})


# --- General image upload (avatar, background) ---
@app.route("/api/upload/image/<image_type>", methods=["POST"])
@require_auth
def upload_image(image_type):
    if image_type not in ("avatar", "background"):
        return jsonify({"error": "invalid image type"}), 400

    if "file" not in request.files:
        return jsonify({"error": "no file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "no file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "file type not allowed"}), 400

    file_data = file.read()
    if len(file_data) > MAX_UPLOAD_SIZE:
        return jsonify({"error": "file too large (max 5MB)"}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    if image_type == "avatar":
        filename = f"phoebe-avatar.{ext}"
    else:
        filename = f"bg-phoebe.{ext}"

    filepath = os.path.join(ASSETS_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(file_data)

    # Update config
    cfg = load_config()
    site = cfg.get("site", {})
    site[image_type] = f"assets/{filename}"
    cfg["site"] = site
    save_config(cfg)

    return jsonify({"ok": True, "path": f"assets/{filename}"})


# --- Sponsors CRUD ---
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
            if "date" in data:
                s["date"] = data["date"].strip()
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
