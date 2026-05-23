import os
import json
from flask import Flask, render_template, redirect, url_for, jsonify, request
import requests

app = Flask(__name__)

API_BASE_URL = os.getenv("API_BASE_URL", "").rstrip("/")
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")
AGENT_METRICS_FILE = "/var/lib/kw-monitoring/agent_metrics.json"


@app.route("/agent/metrics", methods=["POST"])
def receive_agent_metrics():
    try:
        provided_key = request.headers.get("X-Agent-Key", "")

        if not AGENT_API_KEY or provided_key != AGENT_API_KEY:
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json(silent=True)

        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        required_fields = [
                  "device_name",
                  "cpu_usage",
                  "memory_usage",
                  "disk_usage",
                  "status"
        ]

        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            return jsonify({
                "error": "Missing fields",
                "missing_fields": missing_fields
            }), 400

        agent_metrics = {}

        if os.path.exists(AGENT_METRICS_FILE):
            with open(AGENT_METRICS_FILE, "r") as file:
                file_content = file.read().strip()

                if file_content:
                   agent_metrics = json.loads(file_content)

        device_name = data["device_name"]

        agent_metrics[device_name] = {
            "device_name": device_name,
            "cpu_usage": data["cpu_usage"],
            "memory_usage": data["memory_usage"],
            "disk_usage": data["disk_usage"],
            "status": data["status"]
        }

        with open(AGENT_METRICS_FILE, "w") as file:
            json.dump(agent_metrics, file, indent=4)

        return jsonify({
            "message": "Agent metric received",
            "device_name": device_name
        }), 201

    except Exception as error:
        return jsonify({
            "error": "Could not receive agent metric",
            "details": str(error)
        }), 500

def get_metrics_from_api():
    if not API_BASE_URL:
        raise RuntimeError("API_BASE_URL is not configured in the Dashboard App Service.")

    response = requests.get(
        f"{API_BASE_URL}/metrics",
        timeout=10
    )

    response.raise_for_status()
    data = response.json()

    if not isinstance(data, list):
        raise RuntimeError("Monitoring API did not return a list of records.")

    return data

def normalize_status(status):
    status_value = str(status or "unknown").lower()

    if status_value in ["ok", "healthy", "online"]:
        return "online"

    if status_value in ["warning", "warn", "caution"]:
        return "warning"

    if status_value in ["offline", "error", "failed", "down"]:
        return "offline"

    return "unknown"

def sort_metrics_by_timestamp(metrics):
    return sorted(
        metrics,
        key=lambda item: item.get("timestamp", ""),
        reverse=True
    )

@app.route("/")
def index():
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", page_title="Dashboard")

@app.route("/history")
def history():
    return render_template("history.html", page_title="History")

@app.route("/health")
def health():
    if not API_BASE_URL:
        return jsonify({
            "status": "unhealthy",
            "app": "dashboard",
            "error": "API_BASE_URL is not configured"
        }), 500

    return jsonify({
        "status": "healthy",
        "app": "dashboard",
        "api_base_url_configured": True
    }), 200

@app.route("/data/sources/latest")
def latest_sources():
    try:
        metrics = get_metrics_from_api()
        metrics = sort_metrics_by_timestamp(metrics)

        latest_by_device = {}

        for metric in metrics:
            device_name = metric.get("device_name")

            if not device_name:
                continue

            if device_name not in latest_by_device:
                metric["dashboard_status"] = normalize_status(metric.get("status"))
                latest_by_device[device_name] = metric

        return jsonify(list(latest_by_device.values())), 200

    except requests.exceptions.RequestException as error:
        return jsonify({
            "error": "Could not connect to Monitoring API",
            "details": str(error)
        }), 500

    except Exception as error:
        return jsonify({
            "error": "Could not load latest monitoring data",
            "details": str(error)
        }), 500

@app.route("/data/source/<device_name>/latest")
def latest_source(device_name):
    try:
        metrics = get_metrics_from_api()
        metrics = sort_metrics_by_timestamp(metrics)

        for metric in metrics:
            if metric.get("device_name") == device_name:
                metric["dashboard_status"] = normalize_status(metric.get("status"))
                return jsonify(metric), 200

        return jsonify({
            "error": "Source not found"
        }), 404

    except requests.exceptions.RequestException as error:
        return jsonify({
            "error": "Could not connect to Monitoring API",
            "details": str(error)
        }), 500

    except Exception as error:
        return jsonify({
            "error": "Could not load source data",
            "details": str(error)
        }), 500

@app.route("/data/history")
def history_data():
    try:
        metrics = get_metrics_from_api()
        metrics = sort_metrics_by_timestamp(metrics)

        source = request.args.get("source", "all")
        status = request.args.get("status", "all")

        filtered_metrics = []

        for metric in metrics:
            metric["dashboard_status"] = normalize_status(metric.get("status"))

            source_match = source == "all" or metric.get("device_name") == source
            status_match = status == "all" or metric["dashboard_status"] == status.lower()

            if source_match and status_match:
                filtered_metrics.append(metric)

        return jsonify(filtered_metrics), 200

    except requests.exceptions.RequestException as error:
        return jsonify({
            "error": "Could not connect to Monitoring API",
            "details": str(error)
        }), 500

    except Exception as error:
        return jsonify({
            "error": "Could not load history data",
            "details": str(error)
        }), 500

if __name__ == "__main__":
    app.run(debug=True)
