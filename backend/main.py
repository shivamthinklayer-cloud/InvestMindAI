from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
import webbrowser
import threading
import time

from pipeline import run_pipeline

# ─────────────────────────────────────────
# SETUP PATHS
# ─────────────────────────────────────────

# This file is in: IMAI/backend/main.py
# Frontend is in:  IMAI/frontend/index.html

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = BASE_DIR  # index.html is in same folder as main.py              # Clean absolute path

print(f"Backend  folder : {BASE_DIR}")
print(f"Frontend folder : {FRONTEND_DIR}")
print(f"index.html path : {os.path.join(FRONTEND_DIR, 'index.html')}")
print(f"index.html exists: {os.path.exists(os.path.join(FRONTEND_DIR, 'index.html'))}")

# ─────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────

app = Flask(__name__)
CORS(app)


# ─────────────────────────────────────────
# SERVE FRONTEND
# ─────────────────────────────────────────

@app.route("/")
def index():
    """Serve index.html from frontend folder."""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    """Serve any static file from frontend folder."""
    # Don't catch API routes
    if filename.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(FRONTEND_DIR, filename)


# ─────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    try:
        data        = request.get_json(force=True)
        ticker      = data.get("ticker", "").strip().upper()
        stock_name  = data.get("stock_name", "").strip()
        user_option = data.get("user_option", "Want to buy").strip()

        if not ticker:
            return jsonify({"status": "error", "message": "ticker is required"}), 400
        if not stock_name:
            return jsonify({"status": "error", "message": "stock_name is required"}), 400

        # Auto add .NS
        if "." not in ticker:
            ticker += ".NS"

        csv_path = os.path.join(BASE_DIR, f"stock_data_{ticker.replace('.','_')}.csv")

        print(f"\n▶ Analyzing: {ticker} | {stock_name} | {user_option}")

        result = run_pipeline(
            ticker      = ticker,
            stock_name  = stock_name,
            user_option = user_option,
            csv_path    = csv_path,
        )

        return jsonify({
            "status": result["status"],
            "data":   result["output"],
            "time_s": result["total_time_s"],
        })

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────
# AUTO OPEN BROWSER
# ─────────────────────────────────────────

def open_browser():
    time.sleep(2)
    webbrowser.open("http://localhost:5000")


# ─────────────────────────────────────────
# START
# ─────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  🚀 IMAI Stock Analyzer")
    print("  🌐 http://localhost:5000")
    print("="*50 + "\n")

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=False, host="0.0.0.0", port=5000)