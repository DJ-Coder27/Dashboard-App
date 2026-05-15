import os
from flask import Flask, render_template, redirect, url_for, jsonify, request
import requests

app = Flask(__name__)

# This will be configured later in Azure App Service.
# For now, we leave it empty so the dashboard can still run with sample data.
API_BASE_URL = os.getenv("API_BASE_URL", "").rstrip("/")

def get_sample_metrics():
    """
    Temporary sample data.
    This lets us test the dashboard layout before connecting it to the real API.
    Later, the dashboard will read from the existing Monitoring API.
    """
    return [
        {
            "id": 1,
            "device_name": "dc-01",
            "cpu_usage": 32,
            "memory_usage": 56,
            "disk_usage": 68,
            "status": "Online",
            "timestamp": "2026-05-15T12:30:00"
        },
        {
            "id": 2,
            "device_name": "file-server-01",
            "cpu_usage": 42,
            "memory_usage": 68,
            "disk_usage": 92,
            "status": "Warning",
            "timestamp": "2026-05-15T12:30:00"
        },
        {
            "id": 3,
            "device_name": "linux-server-01",
            "cpu_usage": 25,
            "memory_usage": 48,
            "disk_usage": 51,
            "status": "Online",
            "timestamp": "2026-05-15T12:28:00"
        }
    ]


def get_metrics_from_api():
    """
    Gets monitoring data from the existing API App Service.
    The API already has GET /metrics, so the dashboard can read from that endpoint.
    """
    if not API_BASE_URL:
        return get_sample_metrics()

    response = requests.get(f"{API_BASE_URL}/metrics", timeout=10)
    response.raise_for_status()
    return response.json()


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", page_title="Dashboard")


@app.route("/history")
def history():
    return render_template("history.html", page_title="History")


@app.route("/data/sources/latest")
def latest_sources():
    try:
        metrics = get_metrics_from_api()

        latest_by_device = {}

        for metric in metrics:
            device_name = metric.get("device_name")

            if not device_name:
                continue

            if device_name not in latest_by_device:
                latest_by_device[device_name] = metric

        return jsonify(list(latest_by_device.values())), 200

    except Exception as error:
        return jsonify({
            "error": "Could not load latest monitoring data",
            "details": str(error)
        }), 500


@app.route("/data/source/<device_name>/latest")
def latest_source(device_name):
    try:
        metrics = get_metrics_from_api()

        for metric in metrics:
            if metric.get("device_name") == device_name:
                return jsonify(metric), 200

        return jsonify({"error": "Source not found"}), 404

    except Exception as error:
        return jsonify({
            "error": "Could not load source data",
            "details": str(error)
        }), 500


@app.route("/data/history")
def history_data():
    try:
        metrics = get_metrics_from_api()

        source = request.args.get("source", "all")
        status = request.args.get("status", "all")

        filtered_metrics = []

        for metric in metrics:
            source_match = source == "all" or metric.get("device_name") == source
            status_match = status == "all" or metric.get("status", "").lower() == status.lower()

            if source_match and status_match:
                filtered_metrics.append(metric)

        return jsonify(filtered_metrics), 200

    except Exception as error:
        return jsonify({
            "error": "Could not load history data",
            "details": str(error)
        }), 500

if __name__ == "__main__":
    app.run(debug=True)