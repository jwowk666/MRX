from flask import Flask, request, jsonify
import time

app = Flask(__name__)

# قائمة تتبع الطلبات لمنع هجمات DDoS (Rate Limiting)
ip_requests = {}
BANNED_IPS = set()

# إعدادات الحماية: 10 طلبات كحد أقصى في الثانية لكل IP
MAX_REQUESTS_PER_SEC = 10
TIME_WINDOW = 1

@app.before_request
def ddos_firewall():
    client_ip = request.remote_addr
    current_time = time.time()

    if client_ip in BANNED_IPS:
        return jsonify({"status": 403, "message": "Access Denied by MRX Firewall"}), 403

    if client_ip not in ip_requests:
        ip_requests[client_ip] = []

    # تنقية الطلبات القديمة
    ip_requests[client_ip] = [t for t in ip_requests[client_ip] if current_time - t < TIME_WINDOW]

    if len(ip_requests[client_ip]) >= MAX_REQUESTS_PER_SEC:
        BANNED_IPS.add(client_ip)
        return jsonify({"status": 429, "message": "DDoS Attempt Detected. IP Blocked."}), 429

    ip_requests[client_ip].append(current_time)

@app.route('/')
def home():
    return "MRX Store Firewall Status: ACTIVE (100% Secure)"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

