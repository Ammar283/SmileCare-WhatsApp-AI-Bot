import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import re
import time

app = Flask(__name__)

GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
GROQ_MODEL         = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_URL       = "https://api.groq.com/openai/v1/chat/completions"

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

Booking: Customer shares name and number, team calls within 2 hours to confirm.
Payment: Cash, EasyPaisa, JazzCash accepted. No insurance.

=== RULES ===
1. Never quote prices not listed above.
2. For unknown services say: "Please call us at 0300-0000000 for details."
3. Always end with a follow-up question to keep the conversation going.
4. If customer wants to book, ask: "Please share your name and WhatsApp number and our team will call you within 2 hours to confirm your slot."
5. Be warm and friendly — this is a healthcare business.
6. If the message is very short like "?" or "k" or a single character, ask them to clarify what they need help with."""

# Conversation history per user
conversations = {}

# Track last message time per user to avoid duplicate processing
last_message_time = {}

def get_groq_reply(user_phone, user_message):
    """Call Groq API with conversation history and return reply."""
    if user_phone not in conversations:
        conversations[user_phone] = []

    conversations[user_phone].append({
        "role": "user",
        "content": user_message
    })

    # Keep last 10 messages
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

    print(f"[GROQ] Sending to model={GROQ_MODEL}")
    response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=20)
    print(f"[GROQ] Status: {response.status_code}")

    response.raise_for_status()
    reply = response.json()["choices"][0]["message"]["content"].strip()

    conversations[user_phone].append({
        "role": "assistant",
        "content": reply
    })

    return reply

def send_telegram_alert(sender_phone, message):
    """Alert you on Telegram when someone shares their number."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        text = (
            f"🔔 New WhatsApp Lead!\n\n"
            f"Phone: {sender_phone}\n"
            f"Message: {message}\n"
            f"Time: {datetime.now().strftime('%d %b %Y, %H:%M')}\n"
            f"Reply: wa.me/{sender_phone.replace('+', '')}"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=5)
        print(f"[TELEGRAM] Alert sent for {sender_phone}")
    except Exception as e:
        print(f"[TELEGRAM] Error: {e}")

def has_phone_number(message):
    """Detect Pakistani phone numbers."""
    pattern = r'(\+92|0092|0)?[3][0-9]{9}'
    return bool(re.search(pattern, message))

def is_duplicate_message(user_phone, message):
    """Prevent processing the exact same message twice within 3 seconds."""
    now = time.time()
    key = f"{user_phone}:{message}"
    if key in last_message_time:
        if now - last_message_time[key] < 3:
            print(f"[DUPLICATE] Skipping duplicate message from {user_phone}")
            return True
    last_message_time[key] = now
    return False

@app.route("/webhook", methods=["POST"])
def webhook():
    """Main endpoint — Twilio calls this for every incoming WhatsApp message."""
    incoming_msg = request.values.get("Body", "").strip()
    sender       = request.values.get("From", "")
    sender_phone = sender.replace("whatsapp:", "")

    print(f"\n[WEBHOOK] {'='*40}")
    print(f"[WEBHOOK] From: {sender_phone}")
    print(f"[WEBHOOK] Message: '{incoming_msg}'")

    resp = MessagingResponse()

    # Ignore empty messages
    if not incoming_msg:
        print("[WEBHOOK] Empty message — ignoring")
        return str(resp)

    # Ignore duplicate messages (Twilio sometimes sends twice)
    if is_duplicate_message(sender_phone, incoming_msg):
        return str(resp)

    # Check API key
    if not GROQ_API_KEY:
        print("[ERROR] GROQ_API_KEY not set!")
        resp.message("Configuration error. Please contact admin.")
        return str(resp)

    try:
        reply = get_groq_reply(sender_phone, incoming_msg)
        print(f"[SUCCESS] Reply generated: {reply[:80]}...")

        # Alert via Telegram if message contains a phone number (lead!)
        if has_phone_number(incoming_msg):
            send_telegram_alert(sender_phone, incoming_msg)
            print(f"[LEAD] Phone number detected — Telegram alert sent")

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "unknown"
        body   = e.response.text[:200] if e.response else "no response"
        print(f"[ERROR] HTTP {status} from Groq: {body}")
        if status == 429:
            reply = "I am a bit busy right now. Please try again in a moment or call us at 0300-0000000."
        elif status == 401:
            reply = "Authentication error. Please contact admin."
        else:
            reply = "Sorry, I am having a technical issue. Please call us at 0300-0000000."
    except requests.exceptions.Timeout:
        print("[ERROR] Groq API timed out after 20s")
        reply = "Response is taking longer than usual. Please try again or call 0300-0000000."
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        reply = "Sorry, I am having a technical issue. Please call us at 0300-0000000."

    resp.message(reply)
    return str(resp)

@app.route("/", methods=["GET"])
def health():
    """Health check page — visit your Railway URL to verify everything is set."""
    lines = [
        f"status        : live ✓",
        f"groq_key      : {'SET (' + GROQ_API_KEY[:8] + '...)' if GROQ_API_KEY else 'MISSING ✗'}",
        f"twilio_sid    : {'SET' if TWILIO_ACCOUNT_SID else 'MISSING ✗'}",
        f"telegram      : {'SET' if TELEGRAM_BOT_TOKEN else 'not set (optional)'}",
        f"model         : {GROQ_MODEL}",
        f"active_users  : {len(conversations)}",
        f"uptime_check  : {datetime.now().strftime('%d %b %Y %H:%M:%S')}",
    ]
    return "\n".join(lines), 200, {"Content-Type": "text/plain"}

@app.route("/test-groq", methods=["GET"])
def test_groq():
    """Visit /test-groq to verify Groq API is working."""
    if not GROQ_API_KEY:
        return "ERROR: GROQ_API_KEY not set in Railway Variables", 500
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user",   "content": "Say exactly: Bot is working perfectly!"}
            ],
            "max_tokens": 20
        }
        r = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            reply = r.json()["choices"][0]["message"]["content"]
            return f"✓ Groq API working!\nModel: {GROQ_MODEL}\nResponse: {reply}", 200
        else:
            return f"✗ Groq error {r.status_code}: {r.text}", 500
    except Exception as e:
        return f"✗ Exception: {type(e).__name__}: {e}", 500

@app.route("/reset/<phone>", methods=["GET"])
def reset_conversation(phone):
    """Visit /reset/+923001234567 to clear a user's conversation history."""
    key = f"+{phone}" if not phone.startswith("+") else phone
    if key in conversations:
        del conversations[key]
        return f"Conversation reset for {key}", 200
    return f"No conversation found for {key}", 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[STARTUP] SmileCare Bot starting on port {port}")
    print(f"[STARTUP] Groq model: {GROQ_MODEL}")
    print(f"[STARTUP] API key set: {bool(GROQ_API_KEY)}")
    app.run(host="0.0.0.0", port=port, debug=False)
