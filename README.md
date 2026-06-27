# SmileCare WhatsApp AI Bot

A WhatsApp chatbot powered by Claude AI, built with Python + Flask + Twilio.

## Setup in 5 steps

### Step 1 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 2 — Fill in your credentials in bot.py
Open bot.py and fill in:
- ANTHROPIC_API_KEY     → from console.anthropic.com
- TWILIO_ACCOUNT_SID   → from twilio.com/console
- TWILIO_AUTH_TOKEN    → from twilio.com/console
- TELEGRAM_BOT_TOKEN   → from @BotFather on Telegram
- TELEGRAM_CHAT_ID     → from @userinfobot on Telegram

### Step 3 — Set up Twilio WhatsApp sandbox
1. Go to twilio.com → Console → Messaging → WhatsApp Sandbox
2. Follow instructions to connect your phone to the sandbox
3. Set the "When a message comes in" webhook URL to:
   https://YOUR-RAILWAY-URL.railway.app/webhook

### Step 4 — Deploy to Railway (free)
1. Push this folder to a GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub
3. Select your repo — Railway auto-detects Python and deploys
4. Copy your Railway URL and paste it into Twilio webhook field

### Step 5 — Test it
Send "Hi" to the Twilio sandbox WhatsApp number from your phone.
You should get a reply from the bot within 3 seconds!

## Google Sheets setup (optional but impressive for demo)
1. Create a Google Cloud project
2. Enable Google Sheets API
3. Create a service account and download credentials.json
4. Place credentials.json in the same folder as bot.py
5. Share your Google Sheet with the service account email

## Customising for a real client
Replace everything inside === CLINIC INFORMATION === in the SYSTEM_PROMPT
with the client's actual business info. The rest of the code stays the same.
