import os
import json
import uuid
from datetime import timedelta
from functools import wraps
from urllib.parse import urlencode

import msal
import requests
from flask import Flask, render_template, redirect, url_for, jsonify, request, session

app = Flask(__name__)

# Flask session settings
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

# Monitoring API settings
API_BASE_URL = os.getenv("API_BASE_URL", "").rstrip("/")
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")
AGENT_METRICS_FILE = "/var/lib/kw-monitoring/agent_metrics.json"

# Microsoft Entra ID settings
ENTRA_CLIENT_ID = os.getenv("ENTRA_CLIENT_ID", "")
ENTRA_CLIENT_SECRET = os.getenv("ENTRA_CLIENT_SECRET", "")
ENTRA_TENANT_ID = os.getenv("ENTRA_TENANT_ID", "")
ENTRA_REDIRECT_URI = os.getenv(
    "ENTRA_REDIRECT_URI",
    "https://dashboard.knowledgehub.local/callback"
)

POST_LOGOUT_REDIRECT_URI = os.getenv(
    "POST_LOGOUT_REDIRECT_URI",
    "https://dashboard.knowledgehub.local/signed-out"
)

ENTRA_AUTHORITY = f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}" if ENTRA_TENANT_ID else ""
ENTRA_SCOPES = os.getenv("ENTRA_SCOPES", "User.Read").split()

def is_entra_configured():
    return all([
        ENTRA_CLIENT_ID,
        ENTRA_CLIENT_SECRET,
        ENTRA_TENANT_ID,
        ENTRA_REDIRECT_URI
    ])

def build_msal_app():
    return msal.ConfidentialClientApplication(
        ENTRA_CLIENT_ID,
        authority=ENTRA_AUTHORITY,
        client_credential=ENTRA_CLIENT_SECRET
    )

def safe_next_url(next_url):
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url

    return url_for("dashboard")


def login_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))

        return route_function(*args, **kwargs)

    return wrapper

@app.route("/login")
def login():
    if not is_entra_configured():
        return jsonify({
            "error": "Microsoft Entra ID authentication is not configured on the server."
        }), 500

    session["state"] = str(uuid.uuid4())
    session["next_url"] = safe_next_url(request.args.get("next"))

    auth_url = build_msal_app().get_authorization_request_url(
        scopes=ENTRA_SCOPES,
        state=session["state"],
        redirect_uri=ENTRA_REDIRECT_URI
    )

    return redirect(auth_url)

@app.route("/callback")
def callback():
    if request.args.get("state") != session.get("state"):
        return jsonify({"error": "Invalid authentication state."}), 400

    if request.args.get("error"):
        return jsonify({
            "error": request.args.get("error"),
            "description": request.args.get("error_description")
        }), 400

    if not request.args.get("code"):
        return jsonify({"error": "No authorization code was returned by Microsoft Entra ID."}), 400

    result = build_msal_app().acquire_token_by_authorization_code(
        request.args["code"],
        scopes=ENTRA_SCOPES,
        redirect_uri=ENTRA_REDIRECT_URI
    )

    if "error" in result:
        return jsonify({
            "error": result.get("error"),
            "description": result.get("error_description")
        }), 400

    claims = result.get("id_token_claims", {})

    session.permanent = True
    session["user"] = {
        "name": claims.get("name", "Authenticated user"),
        "email": claims.get("preferred_username") or claims.get("email") or claims.get("upn", ""),
        "user_id": claims.get("oid", "")
    }

    next_url = session.pop("next_url", url_for("dashboard"))
    session.pop("state", None)

    return redirect(next_url)

@app.route("/logout")
def logout():
    session.clear()

    if not ENTRA_TENANT_ID:
        return redirect(url_for("signed_out"))

    logout_params = urlencode({
        "post_logout_redirect_uri": POST_LOGOUT_REDIRECT_URI
    })

    return redirect(
        f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/oauth2/v2.0/logout?{logout_params}"
    )

@app.route("/signed-out")
def signed_out():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Signed out</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: #f4f6f8;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }

            .box {
                background: white;
                padding: 32px;
                border-radius: 12px;
                box-shadow: 0 4px 16px rgba(0,0,0,0.1);
                text-align: center;
            }

            a {
                display: inline-block;
                margin-top: 16px;
                padding: 10px 16px;
                background: #1f2937;
                color: white;
                text-decoration: none;
                border-radius: 8px;
            }
        </style>
    </head>
    <body>
        <div class="box">
            <h2>You have been signed out</h2>
            <p>Your dashboard session has been cleared.</p>
            <a href="/login">Sign in again</a>
        </div>
    </body>
    </html>
    """

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
    if session.get("user"):
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", page_title="Dashboard")

@app.route("/history")
@login_required
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
@login_required
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
@login_required
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
@login_required
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