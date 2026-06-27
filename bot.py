import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import re

app = Flask(__name__)

GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

GROQ_MODEL   = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are the AI WhatsApp assistant for SmileCare Dental Clinic in Karachi, Pakistan.

Your job is to answer customer questions in a friendly, professional way.
Always reply in the same language the customer uses (Urdu or English).
Keep replies short — maximum 3-4 sentences.
Never make up information not listed below.
If you do not know something, say: "Our team will contact you shortly for that."

=== CLINIC INFORMATION ===
Name: SmileCare Dental Clinic
Location: Shop 5, Block B, Clifton, Karachi
Phone: 0300-0000000
Timings: Monday to Saturday 10am to 8pm | Sunday: Closed

Services and Prices:
- Consultation: PKR 500
- Teeth cleaning (scaling): PKR 2,500
- Tooth extraction: PKR 1,500 to 3,000
- Filling (composite): PKR 3,000 per tooth
- Root canal: PKR 8,000 to 15,000
- Teeth whitening: PKR 12,000
- Braces (metal): PKR 45,000 total
- Dental implant: PKR 80,000 per implant

Doctors:
- Dr. Sara Ahmed — General Dentist (10 years experience)
- Dr. Khalid Hussain — Orthodontist (braces specialist)

Booking: Customer shares name and number, team calls within 2 hours.
Payment: Cash, EasyPaisa, JazzCash accepted. No insurance.

=== RULES ===
1. Never quote prices not listed above.
2. For unknown services say: "Please call us at 0300-0000000 for details."
3. Always end with a follow-up question to keep the conversation going.
4. If customer seems ready to book, ask for their name and WhatsApp number.
5. Be warm and friendly — this is a healthcare business."""

conversations = {}

def get_groq_reply(user_phone, user_message):
    if user_phone not in conversations:
        conversations[user_phone] = []

    conversations[user_phone].append({
        "role": "user",
        "content": user_message
    })

    history = conversations[user_phone][-10:]

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history,
        "max_tokens": 300,
        "temperature": 0.7
    }

    print(f"[GROQ] Calling API with model={GROQ_MODEL}, key_prefix={GROQ_API_KEY[:8] if GROQ_API_KEY else 'NOT SET'}")

    response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=15)

    print(f"[GROQ] Status code: {response.status_code}")
    print(f"[GROQ] Response: {response.text[:300]}")

    response.raise_for_status()

    reply = response.json()["choices"][0]["message"]["content"].strip()

    conversations[user_phone].append({
        "role": "assistant",
        "content": reply
    })

    return reply

def send_telegram_alert(sender_phone, message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        text = (
            f"New WhatsApp Lead!\n\n"
            f"Phone: {sender_phone}\n"
            f"Message: {message}\n"
            f"Time: {datetime.now().strftime('%d %b %Y, %H:%M')}"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=5)
    except Exception as e:
        print(f"[TELEGRAM] Error: {e}")

def has_phone_number(message):
    pattern = r'(\+92|0092|0)?[3][0-9]{9}'
    return bool(re.search(pattern, message))

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    sender       = request.values.get("From", "")
    sender_phone = sender.replace("whatsapp:", "")

    print(f"[WEBHOOK] From: {sender_phone} | Message: {incoming_msg}")
    print(f"[ENV CHECK] GROQ_API_KEY set: {bool(GROQ_API_KEY)} | starts with: {GROQ_API_KEY[:8] if GROQ_API_KEY else 'EMPTY'}")

    if not incoming_msg:
        return str(MessagingResponse())

    # Safety check — if key missing, say so clearly in logs
    if not GROQ_API_KEY:
        print("[ERROR] GROQ_API_KEY is not set in Railway Variables!")
        resp = MessagingResponse()
        resp.message("Bot config error: API key missing. Admin has been notified.")
        return str(resp)

    try:
        reply = get_groq_reply(sender_phone, incoming_msg)
        print(f"[SUCCESS] Reply: {reply[:100]}")
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] HTTP error from Groq: {e}")
        print(f"[ERROR] Response body: {e.response.text if e.response else 'no response'}")
        reply = "Sorry, I am having a technical issue. Please call us at 0300-0000000."
    except requests.exceptions.Timeout:
        print("[ERROR] Groq API timed out")
        reply = "Sorry, response took too long. Please try again or call 0300-0000000."
    except Exception as e:
        print(f"[ERROR] Unexpected error: {type(e).__name__}: {e}")
        reply = "Sorry, I am having a technical issue. Please call us at 0300-0000000."

    if has_phone_number(incoming_msg):
        send_telegram_alert(sender_phone, incoming_msg)

    resp = MessagingResponse()
    resp.message(reply)
    return str(resp)

@app.route("/", methods=["GET"])
def health():
    return (
        f"status: live | "
        f"groq_key: {'SET (' + GROQ_API_KEY[:8] + '...)' if GROQ_API_KEY else 'MISSING'} | "
        f"twilio: {'SET' if TWILIO_ACCOUNT_SID else 'MISSING'} | "
        f"model: {GROQ_MODEL}"
    ), 200

@app.route("/test-groq", methods=["GET"])
def test_groq():
    """Visit /test-groq in browser to test the Groq API directly."""
    if not GROQ_API_KEY:
        return "ERROR: GROQ_API_KEY not set in Railway Variables", 500
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user",   "content": "Reply with exactly: Groq is working!"}
            ],
            "max_tokens": 20
        }
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=15)
        print(f"[TEST] Groq status: {response.status_code}")
        print(f"[TEST] Groq response: {response.text}")
        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            return f"Groq API working! Response: {reply}", 200
        else:
            return f"Groq API error {response.status_code}: {response.text}", 500
    except Exception as e:
        return f"Exception: {type(e).__name__}: {e}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
