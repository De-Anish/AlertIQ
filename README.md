# 📖 Emergency Alert System – README

This project is an **Emergency Alert System** built with **Flask (Python)**, **MySQL (Aiven Cloud)**, and **Twilio (SMS)**.  
It allows users to:
- Signup/Login using **OTP-based email authentication**  
- Add and manage up to **3 nominees** (emergency contacts)  
- Send **emergency alerts** (classified automatically by ML model) with **location sharing**  
- Notify nominees via **Twilio SMS**  
- View past emergency history  

---

## 🚀 API Endpoints

### 1️⃣ Request OTP
**POST** `/auth/request-otp`  

Request an OTP to be sent to the user’s email.  

#### Request Body
```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "phone": "+917001209139"
}
```

#### Response
```json
{
  "detail": "OTP sent"
}
```

---

### 2️⃣ Verify OTP
**POST** `/auth/verify-otp`  

Verify OTP and activate the user.  

#### Request Body
```json
{
  "email": "user@example.com",
  "otp": "123456"
}
```

#### Response
```json
{
  "detail": "verified",
  "user_id": 1
}
```

---

### 3️⃣ List Nominees
**GET** `/me/nominees?email=user@example.com`  

Fetch nominees for a user.  

#### Response
```json
{
  "nominees": [
    { "id": 1, "name": "Alice", "phone": "+919876543210" },
    { "id": 2, "name": "Bob", "phone": "+917001234567" }
  ]
}
```

---

### 4️⃣ Add Nominee
**POST** `/me/nominees`  

Add a new nominee (max 3 per user).  

#### Request Body
```json
{
  "email": "user@example.com",
  "name": "Alice",
  "phone": "+919876543210"
}
```

#### Response
```json
{
  "detail": "added",
  "nominee_id": 1
}
```

---

### 5️⃣ Edit Nominee
**PUT** `/me/nominees/<nominee_id>`  

Update nominee details.  

#### Request Body
```json
{
  "email": "user@example.com",
  "name": "Alice Updated",
  "phone": "+919912345678"
}
```

#### Response
```json
{
  "detail": "nominee updated"
}
```

---

### 6️⃣ Delete Nominee
**DELETE** `/me/nominees/<nominee_id>`  

Remove a nominee.  

#### Request Body
```json
{
  "email": "user@example.com"
}
```

#### Response
```json
{
  "detail": "nominee deleted"
}
```

---

### 7️⃣ Update User Phone
**PUT** `/me/update-phone`  

Change the registered phone number of the user.  

#### Request Body
```json
{
  "email": "user@example.com",
  "phone": "+917009998888"
}
```

#### Response
```json
{
  "detail": "phone updated"
}
```

---

### 8️⃣ Send Emergency
**POST** `/emergency`  

Send an emergency alert (auto-classified + geolocation).  

#### Request Body
```json
{
  "email": "user@example.com",
  "type": "fire",
  "details": "There is smoke in the kitchen",
  "latitude": 28.6139,
  "longitude": 77.2090
}
```

#### Response
```json
{
  "detail": "emergency recorded",
  "results": [
    {
      "nominee": "+919876543210",
      "success": true,
      "sid": "SMxxxxxxxxxxxxx"
    },
    {
      "nominee": "+917001234567",
      "success": false,
      "error": "Message blocked due to trial account limit"
    }
  ]
}
```

---

### 9️⃣ Past Emergencies
**GET** `/me/emergencies?email=user@example.com`  

Fetch past emergencies for a user.  

#### Response
```json
{
  "emergencies": [
    {
      "id": 1,
      "type": "fire",
      "details": "There is smoke",
      "created_at": "2025-09-25T07:05:34"
    },
    {
      "id": 2,
      "type": "medical",
      "details": "Accident occurred",
      "created_at": "2025-09-24T16:46:38"
    }
  ]
}
```

---

### 🔟 Prediction API
**POST** `/predict`  

Classify an emergency message using the ML model.  

#### Request Body
```json
{
  "texts": ["There is fire in the building"]
}
```

#### Response
```json
{
  "labels": ["fire"],
  "probabilities": [[0.95, 0.03, 0.02]]
}
```

---

## ⚠️ Twilio Trial Limitations
- SMS can only be sent to **verified numbers**.  
- Messages must be **short** (trial accounts block multi-segment SMS).  
- To remove restrictions, upgrade your Twilio account.  

---

## ✅ Run Locally
```bash
# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run server
python flask_server.py --port 5055
```
# AlertIQ
