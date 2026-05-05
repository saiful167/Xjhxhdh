telebot requests
import time
import random
import string
import sqlite3
import os
from datetime import datetime
import telebot
# আপনার বর্তমান কোডের শুরুতেই (যেখানে অন্যান্য import আছে সেখানে) এই লাইনগুলো যোগ করুন:

import threading
from flask import Flask

# ফ্লাস্ক অ্যাপ (Render এর জন্য পোর্ট বাঁধার কৌশল)
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Magnific Bot is running (polling mode).", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# ব্যাকগ্রাউন্ডে ফ্লাস্ক চালু করুন
threading.Thread(target=run_flask, daemon=True).start()

BOT_TOKEN = "8725024459:AAEcL5waEF9eWGjZ1vCXt1Uo56VnENLag00"
API_KEY = "r3f6PifXWq7w6XLjXJVHFKgMCngyieVW8sySBB38O7"
EXTRACT_PICS_URL = "https://api.extract.pics/v0/extractions"
DEVELOPER_ID = "8725024459"

DB_PATH = '/tmp/bot_database.db'

bot = telebot.TeleBot(BOT_TOKEN)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id TEXT PRIMARY KEY, username TEXT, coins INTEGER, total_downloads INTEGER, refer_token TEXT, referred_by TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS redemptions 
                 (code TEXT PRIMARY KEY, coins INTEGER, created_by TEXT, created_at TEXT, used_by TEXT, used_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS downloads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, url TEXT, images_count INTEGER, timestamp TEXT)''')
    conn.commit()
    return conn

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result

def create_user(user_id, username, refer_token=None, referred_by=None):
    conn = get_db()
    c = conn.cursor()
    if not get_user(user_id):
        c.execute("INSERT INTO users (user_id, username, coins, total_downloads, refer_token, referred_by) VALUES (?, ?, ?, ?, ?, ?)",
                  (user_id, username, 3, 0, refer_token, referred_by))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def update_coins(user_id, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def get_coins(user_id):
    user = get_user(user_id)
    return user[2] if user else 0

def generate_refer_token():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def generate_redeem_code(coins):
    conn = get_db()
    c = conn.cursor()
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    c.execute("INSERT INTO redemptions (code, coins, created_by, created_at) VALUES (?, ?, ?, ?)",
              (code, coins, DEVELOPER_ID, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return code

def redeem_code(code, user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM redemptions WHERE code = ? AND used_by IS NULL", (code,))
    redemption = c.fetchone()
    if redemption:
        c.execute("UPDATE redemptions SET used_by = ?, used_at = ? WHERE code = ?", 
                  (user_id, datetime.now().isoformat(), code))
        conn.commit()
        update_coins(user_id, redemption[1])
        conn.close()
        return True, redemption[1]
    conn.close()
    return False, 0

def start_extraction(url):
    try:
        res = requests.post(
            EXTRACT_PICS_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"url": url},
            timeout=30
        )
        if res.status_code in [200, 201]:
            data = res.json()
            return data["data"]["id"], data["data"]["status"]
        return None, None
    except:
        return None, None

def get_extraction_result(extraction_id):
    try:
        res = requests.get(
            f"{EXTRACT_PICS_URL}/{extraction_id}",
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=30
        )
        if res.status_code == 200:
            data = res.json()
            return data["data"]["status"], data["data"].get("images", [])
        return "error", []
    except:
        return "error", []

def extract_image_urls(images):
    urls = []
    for img in images:
        url = img.get("url", "")
        if ("img.magnific.com/premium-photo/" in url or "img.magnific.com/premium-vector/" in url) and "?w=" not in url:
            if url not in urls:
                urls.append(url)
    return urls

def is_valid_magnific_url(url):
    valid_patterns = ['premium-photo', 'premium-vector']
    for pattern in valid_patterns:
        if pattern in url and 'magnific.com' in url:
            return True
    return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or "NoUsername"
    
    args = message.text.split()
    refer_token = args[1] if len(args) > 1 else None
    
    referred_by = None
    if refer_token:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE refer_token = ?", (refer_token,))
        ref_user = c.fetchone()
        conn.close()
        if ref_user:
            referred_by = ref_user[0]
            update_coins(referred_by, 2)
            try:
                bot.send_message(referred_by, f"🎉 Someone joined using your referral! +2 coins")
            except:
                pass
    
    if not get_user(user_id):
        new_token = generate_refer_token()
        create_user(user_id, username, new_token, referred_by)
        if referred_by:
            bot.reply_to(message, f"✅ Welcome! You got 3 free coins!")
        else:
            bot.reply_to(message, "✅ Welcome! You have 3 free coins.\n\nUse /help to see commands.")
    else:
        bot.reply_to(message, "Welcome back! Use /help to see commands.")

@bot.message_handler(commands=['help'])
def show_help(message):
    help_text = """📖 AVAILABLE COMMANDS

/download [URL] - Extract images (Photo or Vector)
/coin - Check your balance
/redeem [CODE] - Redeem coin code
/refer - Get referral link
/status - Your statistics
/user - Your info
/help - This menu

Supported: premium-photo & premium-vector
1 coin = 1 extraction
Refer = 2 coins"""
    
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['download'])
def handle_download(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or "NoUsername"
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Usage: /download [URL]\n\nExample: /download https://www.magnific.com/premium-photo/xxxxx.htm")
        return
    
    url = args[1]
    
    if not is_valid_magnific_url(url):
        bot.reply_to(message, "❌ Please provide a valid Magnific URL.\n\nSupported: premium-photo or premium-vector")
        return
    
    user = get_user(user_id)
    if not user:
        create_user(user_id, username)
        user = get_user(user_id)
    
    coins = user[2]
    
    if coins < 1:
        bot.reply_to(message, "❌ No coins left!\n\nGet more:\n• /refer - Invite friends (2 coins each)\n• /redeem [CODE] - Use redeem code")
        return
    
    bot.reply_to(message, "🚀 Starting extraction...\n⏳ Please wait 50 seconds.")
    
    extraction_id, status = start_extraction(url)
    
    if not extraction_id:
        bot.reply_to(message, "❌ Extraction failed. Please try again.")
        return
    
    bot.send_message(message.chat.id, f"✅ Extraction started!\n🆔 ID: `{extraction_id}`\n⏳ 50 seconds remaining...")
    
    time.sleep(50)
    
    final_status, images = get_extraction_result(extraction_id)
    
    if final_status == "done" and images:
        image_urls = extract_image_urls(images)
        
        if image_urls:
            update_coins(user_id, -1)
            
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO downloads (user_id, url, images_count, timestamp) VALUES (?, ?, ?, ?)",
                      (user_id, url, len(image_urls), datetime.now().isoformat()))
            c.execute("UPDATE users SET total_downloads = total_downloads + 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            
            bot.send_message(message.chat.id, f"✅ Found {len(image_urls)} images! Sending now...")
            
            for i, img_url in enumerate(image_urls[:10]):
                try:
                    bot.send_photo(message.chat.id, img_url, caption=f"📸 Image {i+1}/{len(image_urls)}")
                except:
                    pass
            
            if len(image_urls) > 10:
                bot.send_message(message.chat.id, f"✅ Sent first 10 images. Total {len(image_urls)} images found.")
            
            bot.send_message(message.chat.id, f"🎉 Complete! You have {get_coins(user_id)} coins left.")
        else:
            bot.reply_to(message, "❌ No valid images found in this page.")
    else:
        bot.reply_to(message, "❌ Extraction failed or still pending. Please try again.")

@bot.message_handler(commands=['coin'])
def check_coins(message):
    user_id = str(message.from_user.id)
    coins = get_coins(user_id)
    bot.reply_to(message, f"💰 Your balance: {coins} coins\n\n1 coin = 1 extraction")

@bot.message_handler(commands=['refer'])
def get_refer_link(message):
    user_id = str(message.from_user.id)
    user = get_user(user_id)
    
    if not user:
        create_user(user_id, message.from_user.username or "NoUsername")
        user = get_user(user_id)
    
    refer_token = user[4]
    bot_link = f"https://t.me/{bot.get_me().username}?start={refer_token}"
    
    bot.reply_to(message, f"🔗 YOUR REFERRAL LINK\n\n{bot_link}\n\n🎁 Each friend = 2 coins!\nShare this link with your friends.")

@bot.message_handler(commands=['status'])
def show_status(message):
    user_id = str(message.from_user.id)
    user = get_user(user_id)
    
    if user:
        coins = user[2]
        downloads = user[3]
        
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM downloads WHERE user_id = ?", (user_id,))
        total = c.fetchone()[0]
        conn.close()
        
        bot.reply_to(message, f"📊 YOUR STATISTICS\n\n💰 Coins: {coins}\n📥 Total downloads: {downloads}\n🖼️ Images downloaded: {total}\n\nKeep extracting!")
    else:
        bot.reply_to(message, "Send /start first")

@bot.message_handler(commands=['user'])
def show_user_info(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or "NoUsername"
    coins = get_coins(user_id)
    bot.reply_to(message, f"👤 USER INFO\n\n🆔 ID: {user_id}\n📛 Username: @{username}\n💰 Coins: {coins}")

@bot.message_handler(commands=['redeem'])
def handle_redeem(message):
    user_id = str(message.from_user.id)
    args = message.text.split()
    
    if len(args) < 2:
        bot.reply_to(message, "❌ Usage: /redeem [CODE]\n\nExample: /redeem ABC123XYZ789")
        return
    
    code = args[1].upper()
    success, coins = redeem_code(code, user_id)
    
    if success:
        bot.reply_to(message, f"✅ Redeemed {coins} coins!\n💰 New balance: {get_coins(user_id)} coins")
    else:
        bot.reply_to(message, "❌ Invalid or already used code.")

@bot.message_handler(commands=['generate'])
def generate_code(message):
    if str(message.from_user.id) != DEVELOPER_ID:
        bot.reply_to(message, "❌ Admin only command.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Usage: /generate [amount]")
        return
    
    try:
        amount = int(args[1])
        code = generate_redeem_code(amount)
        bot.reply_to(message, f"✅ CODE GENERATED\n\nCode: `{code}`\nAmount: {amount} coins\n\nUse: /redeem {code}")
    except:
        bot.reply_to(message, "❌ Invalid amount.")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if str(message.from_user.id) != DEVELOPER_ID:
        bot.reply_to(message, "❌ Admin only command.")
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT SUM(coins) FROM users")
    total_coins = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM downloads")
    total_downloads = c.fetchone()[0]
    conn.close()
    
    bot.reply_to(message, f"📊 BOT STATISTICS\n\n👥 Total Users: {total_users}\n💰 Total Coins: {total_coins}\n📥 Total Downloads: {total_downloads}")

@bot.message_handler(func=lambda message: True)
def handle_other(message):
    bot.reply_to(message, "❌ Unknown command.\n\nUse /help to see all available commands.")

print("🤖 Magnific Bot is running on Render with polling mode...")
print("✅ Supported: premium-photo & premium-vector")
print("✅ Commands: /start, /download, /coin, /refer, /redeem, /status, /user, /help")
bot.infinity_polling(timeout=20, long_polling_timeout=10)
