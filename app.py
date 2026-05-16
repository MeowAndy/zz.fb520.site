#!/usr/bin/env python3
"""
Sponsor Page API - Generic deployable sponsor/donation page backend.
No hardcoded passwords. First-time setup via /api/setup.
"""
import json
import os
import uuid
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configurable directories - default to relative paths for easy deployment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
STATIC_DIR = os.environ.get("STATIC_DIR", os.path.join(BASE_DIR, "assets"))

SPONSORS_FILE = os.path.join(DATA_DIR, "sponsors.json")
FINANCE_FILE = os.path.join(DATA_DIR, "finance.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB


# --- Helpers ---

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(STATIC_DIR, exist_ok=True)


def load_json(filepath, default=None):
    if default is None:
        default = {}
    if not os.path.exists(filepath):
        return default
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filepath, data):
    ensure_dirs()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_config():
    return load_json(CONFIG_FILE, {})


def save_config(cfg):
    save_json(CONFIG_FILE, cfg)


def load_sponsors():
    return load_json(SPONSORS_FILE, [])


def save_sponsors(sponsors):
    save_json(SPONSORS_FILE, sponsors)


def load_finance():
    return load_json(FINANCE_FILE, {"income": 0, "expense": 0})


def save_finance(data):
    save_json(FINANCE_FILE, data)


def is_setup_done():
    cfg = load_config()
    return "password_hash" in cfg and cfg["password_hash"]


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def recalc_income():
    """Recalculate income from all sponsors."""
    sponsors = load_sponsors()
    total = 0
    for sp in sponsors:
        try:
            amt = sp.get("amount", "").replace("+", "").replace("¥", "").replace(",", "")
            total += float(amt)
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
        if not is_setup_done():
            return jsonify({"error": "not_setup"}), 403
        cfg = load_config()
        password = request.headers.get("X-Admin-Password", "")
        if not password:
            # Try JSON body
            try:
                body = request.get_json(silent=True) or {}
                password = body.get("password", "")
            except Exception:
                pass
        if not check_password_hash(cfg["password_hash"], password):
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# --- Setup ---

@app.route("/api/setup", methods=["GET"])
def setup_status():
    """Check if initial setup is done."""
    return jsonify({"setup_done": is_setup_done()})


@app.route("/api/setup", methods=["POST"])
def do_setup():
    """First-time password setup. Only works if no password is set."""
    if is_setup_done():
        return jsonify({"error": "already_setup"}), 400
    data = request.get_json(silent=True) or {}
    password = data.get("password", "").strip()
    if not password or len(password) < 4:
        return jsonify({"error": "password_too_short"}), 400
    cfg = load_config()
    cfg["password_hash"] = generate_password_hash(password)
    save_config(cfg)
    return jsonify({"ok": True, "message": "Password set successfully"})


# --- Site Config (public read, auth write) ---

@app.route("/api/config", methods=["GET"])
def get_config():
    """Public endpoint: returns site display config (no password hash)."""
    cfg = load_config()
    public_cfg = {
        "title": cfg.get("title", "赞助页"),
        "subtitle": cfg.get("subtitle", ""),
        "description": cfg.get("description", ""),
        "avatar": cfg.get("avatar", "assets/avatar.jpg"),
        "background": cfg.get("background", "assets/bg.jpg"),
        "qr_wechat": cfg.get("qr_wechat", "assets/wechat.jpg"),
        "qr_alipay": cfg.get("qr_alipay", "assets/alipay.jpg"),
        "qr_qq": cfg.get("qr_qq", "assets/qq.jpg"),
        "setup_done": is_setup_done(),
    }
    return jsonify(public_cfg)


@app.route("/api/config", methods=["PUT"])
@require_auth
def update_config():
    """Update site display config (title, subtitle, description)."""
    data = request.get_json(silent=True) or {}
    cfg = load_config()
    for key in ("title", "subtitle", "description"):
        if key in data:
            cfg[key] = data[key].strip()
    save_config(cfg)
    return jsonify({"ok": True})


# --- File Upload ---

@app.route("/api/upload", methods=["POST"])
@require_auth
def upload_file():
    """Upload image file. Query param 'type' = avatar|background|wechat|alipay|qq"""
    upload_type = request.args.get("type", "")
    valid_types = {"avatar", "background", "wechat", "alipay", "qq"}
    if upload_type not in valid_types:
        return jsonify({"error": f"Invalid type. Must be one of: {', '.join(valid_types)}"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    # Check file size
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_UPLOAD_SIZE:
        return jsonify({"error": "File too large (max 5MB)"}), 400

    # Determine filename
    ext = file.filename.rsplit(".", 1)[1].lower()
    type_to_filename = {
        "avatar": f"avatar.{ext}",
        "background": f"bg.{ext}",
        "wechat": f"wechat.{ext}",
        "alipay": f"alipay.{ext}",
        "qq": f"qq.{ext}",
    }
    filename = type_to_filename[upload_type]
    filepath = os.path.join(STATIC_DIR, filename)

    # Remove old files with different extensions
    for old_ext in ALLOWED_EXTENSIONS:
        old_file = os.path.join(STATIC_DIR, type_to_filename[upload_type].rsplit(".", 1)[0] + "." + old_ext)
        if old_file != filepath and os.path.exists(old_file):
            os.remove(old_file)

    file.save(filepath)

    # Update config with new path
    cfg = load_config()
    relative_path = f"assets/{filename}"
    type_to_config_key = {
        "avatar": "avatar",
        "background": "background",
        "wechat": "qr_wechat",
        "alipay": "qr_alipay",
        "qq": "qr_qq",
    }
    cfg[type_to_config_key[upload_type]] = relative_path
    save_config(cfg)

    return jsonify({"ok": True, "path": relative_path})


# --- Sponsors ---

@app.route("/api/sponsors", methods=["GET"])
def get_sponsors():
    return jsonify(load_sponsors())


@app.route("/api/sponsors", methods=["POST"])
@require_auth
def add_sponsor():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    amount = data.get("amount", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    sponsor = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "amount": amount,
        "date": data.get("date", ""),
    }
    sponsors = load_sponsors()
    sponsors.append(sponsor)
    save_sponsors(sponsors)
    recalc_income()
    return jsonify(sponsor), 201


@app.route("/api/sponsors/<sponsor_id>", methods=["PUT"])
@require_auth
def update_sponsor(sponsor_id):
    data = request.get_json(silent=True) or {}
    sponsors = load_sponsors()
    for s in sponsors:
        if s["id"] == sponsor_id:
            if "name" in data:
                s["name"] = data["name"].strip()
            if "amount" in data:
                s["amount"] = data["amount"].strip()
            if "date" in data:
                s["date"] = data["date"].strip()
            save_sponsors(sponsors)
            recalc_income()
            return jsonify(s)
    return jsonify({"error": "not found"}), 404


@app.route("/api/sponsors/<sponsor_id>", methods=["DELETE"])
@require_auth
def delete_sponsor(sponsor_id):
    sponsors = load_sponsors()
    new_sponsors = [s for s in sponsors if s["id"] != sponsor_id]
    if len(new_sponsors) == len(sponsors):
        return jsonify({"error": "not found"}), 404
    save_sponsors(new_sponsors)
    recalc_income()
    return jsonify({"ok": True})


# --- Finance ---

@app.route("/api/finance", methods=["GET"])
def get_finance():
    fin = load_finance()
    income = float(fin.get("income", 0))
    expense = float(fin.get("expense", 0))
    balance = round(income - expense, 2)
    return jsonify({
        "income": income,
        "expense": expense,
        "balance": balance,
        "status": "盈利" if balance >= 0 else "亏损",
    })


@app.route("/api/finance", methods=["PUT"])
@require_auth
def update_finance():
    data = request.get_json(silent=True) or {}
    fin = load_finance()
    if "expense" in data:
        fin["expense"] = float(data["expense"])
    # Income is auto-calculated, but allow manual override
    if "income" in data:
        fin["income"] = float(data["income"])
    save_finance(fin)
    income = float(fin.get("income", 0))
    expense = float(fin.get("expense", 0))
    balance = round(income - expense, 2)
    return jsonify({
        "income": income,
        "expense": expense,
        "balance": balance,
        "status": "盈利" if balance >= 0 else "亏损",
    })


# --- Change Password ---

@app.route("/api/change-password", methods=["POST"])
@require_auth
def change_password():
    """Change admin password (requires current password in X-Admin-Password header)."""
    data = request.get_json(silent=True) or {}
    new_password = data.get("new_password", "").strip()
    if not new_password or len(new_password) < 4:
        return jsonify({"error": "new password too short"}), 400
    cfg = load_config()
    cfg["password_hash"] = generate_password_hash(new_password)
    save_config(cfg)
    return jsonify({"ok": True, "message": "Password changed"})


# --- Static file serving (for development) ---

@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory(STATIC_DIR, filename)


if __name__ == "__main__":
    ensure_dirs()
    print(f"Data dir: {DATA_DIR}")
    print(f"Static dir: {STATIC_DIR}")
    print(f"Setup done: {is_setup_done()}")
    app.run(host="127.0.0.1", port=5100)
