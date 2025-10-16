import os
import pickle
import joblib
from typing import Any, Dict
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text
from datetime import datetime, timedelta
import random
import smtplib
from email.message import EmailMessage
from twilio.rest import Client
from dotenv import load_dotenv
import requests


load_dotenv()

MODEL_PATH = os.path.join(os.path.dirname(__file__), "emergency_classifier.pkl")


DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "defaultdb")
DB_PORT = int(os.getenv("DB_PORT", 3306))
SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


EMAIL_USER = os.getenv("SMTP_USER", "anishde0950@gmail.com")
EMAIL_PASSWORD = os.getenv("SMTP_PASS", "zhan ncer wvtg admu".replace(" ", ""))


TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_FROM = os.getenv("TWILIO_FROM")

if not all([TWILIO_SID, TWILIO_AUTH, TWILIO_FROM]):
    raise RuntimeError("❌ Twilio environment variables missing. Check your .env file.")

print("DEBUG: Using Twilio SID:", TWILIO_SID)

app = Flask(__name__)
CORS(app)
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"ssl_disabled": True}}
app.secret_key = os.getenv("APP_SECRET", "abz002fg FOR SMTP")

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    phone = db.Column(db.String(32), nullable=False)
    verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    nominees = db.relationship('Nominee', backref='user', cascade='all, delete-orphan')

class Nominee(db.Model):
    __tablename__ = 'nominees'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(32), nullable=False)

class Emergency(db.Model):
    __tablename__ = 'emergencies'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    emergency_type = db.Column(db.String(64), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=func.now())


OTP_STORE: Dict[str, Dict[str, Any]] = {}


def send_otp_email(email: str, otp: str):
    subject = "Your OTP Code"
    body = f"Your OTP is: {otp}. It expires in 10 minutes."
    msg = EmailMessage()
    msg["From"] = EMAIL_USER
    msg["To"] = email
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f"[OTP] Sent to {email}")
    except Exception as e:
        print(f"[OTP][ERROR] {e}")

def send_twilio_sms(phone: str, message: str) -> Dict[str, Any]:
    try:
        client = Client(TWILIO_SID, TWILIO_AUTH)
        msg = client.messages.create(body=message, from_=TWILIO_FROM, to=phone)
        print(f"[Twilio] Sent SMS to {phone}, SID={msg.sid}")
        return {"success": True, "sid": msg.sid}
    except Exception as e:
        print(f"[Twilio][ERROR] {e}")
        return {"success": False, "error": str(e)}

def reverse_geocode(lat: float, lon: float) -> str:
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"format": "jsonv2", "lat": lat, "lon": lon, "addressdetails": 1}
        res = requests.get(url, params=params, headers={'User-Agent': 'EmergencyApp'})
        if res.status_code == 200:
            result = res.json()
            return result.get("display_name", "Unknown location")
        return f"Location lookup failed ({res.status_code})"
    except Exception as e:
        return f"Location error: {e}"


try:
    classifier = pickle.load(open(MODEL_PATH, "rb"))
except Exception as exc:
    try:
        classifier = joblib.load(MODEL_PATH)
    except Exception:
        classifier = None
        load_error = exc
else:
    load_error = None


@app.get("/health")
def health() -> Any:
    db_ok, db_err = True, None
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as e:
        db_ok, db_err = False, str(e)
    status = "ok" if (classifier and db_ok) else "degraded"
    return jsonify({
        "status": status,
        "detail": None if status == "ok" else {
            "model": None if classifier else str(load_error),
            "db": db_ok,
            "db_error": db_err,
        }
    })

@app.post("/predict")
def predict() -> Any:
    if classifier is None:
        return jsonify({"detail": f"Model not loaded: {load_error}"}), 503
    body = request.get_json(silent=True) or {}
    texts = body.get("texts")
    if not texts or not isinstance(texts, list):
        return jsonify({"detail": "Body must include 'texts': List[str]"}), 400
    try:
        labels = classifier.predict(texts)
        probs = None
        if hasattr(classifier, "predict_proba"):
            probs = [list(map(float, row)) for row in classifier.predict_proba(texts)]
        return jsonify({"labels": [str(l) for l in labels], "probabilities": probs})
    except Exception as exc:
        return jsonify({"detail": f"Prediction failed: {exc}"}), 500


@app.post('/auth/request-otp')
def request_otp():
    data = request.get_json(silent=True) or {}
    email, name, phone = data.get('email'), data.get('name'), data.get('phone')
    if not email or not phone:
        return jsonify({'detail': 'email and phone required'}), 400
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name=name, phone=phone, verified=False)
        db.session.add(user)
        db.session.commit()
    otp = f"{random.randint(100000, 999999)}"
    OTP_STORE[email] = {"otp": otp, "expires": datetime.utcnow() + timedelta(minutes=10)}
    send_otp_email(email, otp)
    return jsonify({'detail': 'OTP sent'})

@app.post('/auth/verify-otp')
def verify_otp():
    data = request.get_json(silent=True) or {}
    email, otp = data.get('email'), data.get('otp')
    rec = OTP_STORE.get(email)
    if not rec or datetime.utcnow() > rec['expires'] or rec['otp'] != otp:
        return jsonify({'detail': 'invalid or expired OTP'}), 400
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'detail': 'user not found'}), 404
    user.verified = True
    db.session.commit()
    return jsonify({'detail': 'verified', 'user_id': user.id})


@app.get('/me/nominees')
def list_nominees():
    email = request.args.get('email')
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'detail': 'user not found'}), 404
    return jsonify({'nominees': [{"id": n.id, "name": n.name, "phone": n.phone} for n in user.nominees]})

@app.post('/me/nominees')
def add_nominee():
    data = request.get_json(silent=True) or {}
    email, name, phone = data.get('email'), data.get('name'), data.get('phone')
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'detail': 'user not found'}), 404
    if len(user.nominees) >= 3:
        return jsonify({'detail': 'max 3 nominees reached'}), 400
    n = Nominee(user_id=user.id, name=name, phone=phone)
    db.session.add(n)
    db.session.commit()
    return jsonify({'detail': 'added', 'nominee_id': n.id})

@app.put('/me/nominees/<int:nominee_id>')
def update_nominee(nominee_id):
    data = request.get_json(silent=True) or {}
    name, phone = data.get('name'), data.get('phone')
    nominee = Nominee.query.get(nominee_id)
    if not nominee:
        return jsonify({'detail': 'nominee not found'}), 404
    if name: nominee.name = name
    if phone: nominee.phone = phone
    db.session.commit()
    return jsonify({'detail': 'updated'})

@app.delete('/me/nominees/<int:nominee_id>')
def delete_nominee(nominee_id):
    nominee = Nominee.query.get(nominee_id)
    if not nominee:
        return jsonify({'detail': 'nominee not found'}), 404
    db.session.delete(nominee)
    db.session.commit()
    return jsonify({'detail': 'deleted'})


@app.post('/emergency')
def report_emergency():
    data = request.get_json(silent=True) or {}
    email, em_type, details = data.get('email'), data.get('type'), data.get('details')
    lat, lon = data.get('latitude'), data.get('longitude')
    if not email or not em_type:
        return jsonify({'detail': 'email and type required'}), 400
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'detail': 'user not found'}), 404

    em = Emergency(user_id=user.id, emergency_type=em_type, details=details)
    db.session.add(em)
    db.session.commit()

    location_text = ""
    if lat and lon:
        try:
            lat = float(lat); lon = float(lon)
            location_text = f"\n📍 Location: {reverse_geocode(lat, lon)}"
            location_text += f"\n🌐 Maps: https://www.google.com/maps?q={lat},{lon}"
        except Exception as e:
            location_text = f"\n📍 Location error: {e}"

    message = (
        f"ALERT from {user.name or user.email}\n"
        f"Type: {em_type}\n"
        f"Details: {details or 'N/A'}\n"
        f"Maps: https://maps.google.com/?q={lat},{lon}"
    )
    results = []
    for nm in user.nominees[:3]:
        results.append({"nominee": nm.phone, **send_twilio_sms(nm.phone, message)})
    return jsonify({'detail': 'emergency recorded', 'results': results})

@app.get('/me/emergencies')
def list_emergencies():
    email = request.args.get('email')
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'detail': 'user not found'}), 404
    return jsonify({
        'emergencies': [
            {
                "id": e.id,
                "type": e.emergency_type,
                "details": e.details,
                "created_at": e.created_at.strftime("%Y-%m-%d %H:%M:%S")  # ✅ format datetime
            }
            for e in Emergency.query.filter_by(user_id=user.id).order_by(Emergency.created_at.desc())
        ]
    })


@app.get('/ui')
def serve_ui():
    return send_from_directory(os.path.dirname(__file__), 'emergency_frontend.html')


if __name__ == "__main__":
  
    port = int(os.environ.get("PORT", 10000))  # ✅ Use Render’s PORT variable
    app.run(host="0.0.0.0", port=port, debug=False)
