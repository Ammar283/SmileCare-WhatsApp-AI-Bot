import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import re

app = Flask(__name__)

# ============================================================
# CONFIGURATION — fill these in before running
# ============================================================
GROQ_API_KEY        = "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"        # console.groq.com (free)
TWILIO_ACCOUNT_SID  = "AC5f0e5afe24d116ace4d5245e48d2b709"
TWILIO_AUTH_TOKEN   = "c00e9a8cbb38b705ae35aad03c148157 "
TELEGRAM_BOT_TOKEN  = "AAGyl20yfF2tJCp0PTuIOd9Eg-cJ0mRXVUI"
TELEGRAM_CHAT_ID    = "8765556797"

# Groq model — all free, llama is best for chat
GROQ_MODEL = "llama3-8b-8192"
# Other free options:
# "llama3-70b-8192"      — smarter, slightly slower
# "mixtral-8x7b-32768"   — great for long conversations
# "gemma2-9b-it"         — good multilingual (Urdu/English)
# ============================================================

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
4. If customer seems ready to book, ask: "Can I get your name and WhatsApp number so our team can call you?"
5. Be warm and friendly — this is a healthcare business."""

# Conversation history per user (phone number -> list of messages)
conversations = {}

def get_groq_reply(user_phone, user_message):
    """Send message to Groq API and get AI reply."""
    if user_phone not in conversations:
        conversations[user_phone] = []

    # Add user message to history
    conversations[user_phone].append({
        "role": "user",
        "content": user_message
    })

    # Keep last 10 messages to stay within token limits
    history = conversations[user_phone][-10:]

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT}
        ] + history,
        "max_tokens": 300,
        "temperature": 0.7
    }

    response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=15)
    response.raise_for_status()
    data = response.json()
    reply = data["choices"][0]["message"]["content"].strip()

    # Save assistant reply to history
    conversations[user_phone].append({
        "role": "assistant",
        "content": reply
    })

    return reply

def send_telegram_alert(sender_phone, message):
    """Send instant lead notification to your Telegram."""
    try:
        text = (
            f"New WhatsApp Lead!\n\n"
            f"Phone: {sender_phone}\n"
            f"Message: {message}\n"
            f"Time: {datetime.now().strftime('%d %b %Y, %H:%M')}\n\n"
            f"Reply: wa.me/{sender_phone.replace('+', '')}"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")

def has_phone_number(message):
    """Check if message contains a Pakistani phone number."""
    pattern = r'(\+92|0092|0)?[3][0-9]{9}'
    return bool(re.search(pattern, message))

@app.route("/webhook", methods=["POST"])
def webhook():
    """Twilio calls this endpoint when a WhatsApp message arrives."""
    incoming_msg = request.values.get("Body", "").strip()
    sender       = request.values.get("From", "")
    sender_phone = sender.replace("whatsapp:", "")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] {sender_phone}: {incoming_msg}")

    if not incoming_msg:
        return str(MessagingResponse())

    try:
        reply = get_groq_reply(sender_phone, incoming_msg)
    except Exception as e:
        print(f"Groq error: {e}")
        reply = "Sorry, I am having a technical issue. Please call us at 0300-0000000 or try again in a moment."

    # If message has a phone number in it, treat as a lead and alert via Telegram
    if has_phone_number(incoming_msg):
        send_telegram_alert(sender_phone, incoming_msg)

    resp = MessagingResponse()
    resp.message(reply)
    return str(resp)

@app.route("/", methods=["GET"])
def health():
    return "SmileCare WhatsApp Bot is live!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
