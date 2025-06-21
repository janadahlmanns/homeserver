from flask import Flask, request, jsonify, render_template, redirect
import json
import os
from datetime import datetime
import pytz
import uuid
import threading
import time
import requests


app = Flask(__name__, template_folder="templates")
ITEMS_FILE = "pending_items.json"
BERLIN = pytz.timezone("Europe/Berlin")

def load_items():
    if os.path.exists(ITEMS_FILE):
        with open(ITEMS_FILE, "r") as f:
            return json.load(f)
    return {"items": []}

def save_items(data):
    with open(ITEMS_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/add", methods=["POST"])
def add():
    data = load_items()
    new_items = request.get_json()

    if not new_items or "item" not in new_items or "source" not in new_items:
        return jsonify({"error": "Missing item or source"}), 400

    raw = new_items["item"]
    name = new_items["source"]

    def split_items(raw):
        if " und " in raw:
            return [x.strip() for x in raw.split(" und ")]
        elif " " in raw:
            return [{"item": x.strip(), "flag": True} for x in raw.split()]
        else:
            return [raw.strip()]

    split = split_items(raw)
    now = datetime.now(BERLIN).strftime("%Y-%m-%d %H:%M:%S")

    for entry in split:
        if isinstance(entry, dict):
            data["items"].append({
                "id": str(uuid.uuid4()),
                "item": entry["item"],
                "flagged": True,
                "timestamp": now,
                "source": name
            })
        else:
            data["items"].append({
                "id": str(uuid.uuid4()),
                "item": entry,
                "flagged": False,
                "timestamp": now,
                "source": name
            })

    save_items(data)
    return jsonify({"status": "ok"})

@app.route("/rebuy-delete", methods=["POST"])
def rebuy_delete():
    data = load_items()
    item_id = request.form.get("id")
    if item_id:
        data["items"] = [item for item in data["items"] if item["id"] != item_id]
        save_items(data)
    return redirect("/rebuy-dashboard")

@app.route("/rebuy-clear-all", methods=["POST"])
def rebuy_clear_all():
    save_items({"items": []})
    return redirect("/rebuy-dashboard")

@app.route("/rebuy-dashboard")
def rebuy_dashboard():
    data = load_items()
    sorted_items = sorted(data["items"], key=lambda x: x["timestamp"], reverse=True)
    return render_template("rebuy_dashboard.html", items=sorted_items)

def esp_logger():
    log_file = "pool_log.jsonl"
    status_url = "http://192.168.178.91/status"

    while True:
        try:
            response = requests.get(status_url, timeout=5)
            data = response.json()
            data["logged_at"] = datetime.now(BERLIN).isoformat()

            with open(log_file, "a") as f:
                f.write(json.dumps(data) + "\n")

            print("✅ ESP status logged:", data)
        except Exception as e:
            print("⚠️ ESP logging error:", e)

        time.sleep(30)  # wait 30 seconds

@app.route("/pool-log")
def pool_log():
    log_file = "pool_log.jsonl"
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            lines = f.readlines()
            entries = [json.loads(line.strip()) for line in lines if line.strip()]
        return jsonify(entries)
    return jsonify({"error": "No pool log found"}), 404

@app.route("/pool-dashboard")
def pool_dashboard():
    return render_template("pool_dashboard.html")

if __name__ == "__main__":
    threading.Thread(target=esp_logger, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)

