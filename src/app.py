import os
import threading
import logging
import sys
from flask import Flask, jsonify, request
from src.auth import AuthManager
from src.service import OutlookService
from src.outlook_api import OutlookAPI

app = Flask(__name__)
auth_manager = AuthManager()
outlook_api = OutlookAPI(auth=auth_manager)
outlook_service = OutlookService(outlook_api=outlook_api)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

@app.route('/')
def home():
    return "Hello, World!"

@app.route('/health')
def health_check():
    return "OK", 200

@app.route('/notifications', methods=['GET', 'POST'])
def notifications():
    logging.info("Incoming /notifications: %s %s %s", request.method, request.args, request.data)
    
    validation_token = request.args.get("validationToken")
    if validation_token:
        logging.info("Validation token received: %s", validation_token)
        # MUST echo back the token as plain text
        return validation_token, 200, {"Content-Type": "text/plain"}

    # 2) Real notifications (after subscription is active)
    try:
        payload = request.get_json(force=True, silent=True) or {}
    except Exception:
        payload = {}
    logging.info("Notification payload: %s", payload)
    notifications = payload.get("value", [])
    
    if not notifications:
        return "No notifications", 202
    saved_count = outlook_service.handle_notification_batch(notifications)
    
    return jsonify({"status": "Notifications processed",
                    "saved": saved_count}), 202
    
def start_subscription_lifecycle():
    callback_url = os.getenv(
        "PUBLIC_BASE_URL",
        "http://127.0.0.1:8000"
    ) + "/notifications"
    outlook_service.subscription_lifecycle(callback_url)

if __name__ == '__main__':
    t = threading.Thread(target=start_subscription_lifecycle, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=8000)