import os
import time
import glob
import telebot
from yt_dlp import YoutubeDL
from flask import Flask
from threading import Thread

# टेलीग्राम बॉट टोकन (Render Environment Variables से लेगा)
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# Flask ऐप (Render को एक्टिव रखने के लिए पोर्ट बाइंडिंग)
app = Flask('')

@app.route('/')
def home():
    return "Bot is running perfectly!"

def run_flask():
    # Render डिफ़ॉल्ट रूप से 10000 पोर्ट का उपयोग करता है
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# स्टार्ट कमांड
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "नमस्ते! मुझे किसी भी इंस्टाग्राम रील (Reels) का लिंक भेजें, मैं उसे कैप्शन के साथ डाउनलोड करके दूंगा।")

# रील डाउनलोडर लॉजिक
@bot.message_handler(func=lambda message: True)
def download_reel(message):
    url = message.text
    
    # चेक करें कि लिंक इंस्टाग्राम का है या नहीं
    if "instagram.com" not in url:
        bot.reply_to(message, "कृपया केवल वैध इंस्टाग्राम रील (Instagram Reel) का लिंक भेजें।")
        return

    status_msg = bot.reply_to(message, "⏳ आपकी रील प्रोसेस हो रही है, कृपया प्रतीक्षा करें...")

    # yt-dlp कॉन्फ़िगरेशन
    ydl_opts = {
        'format': 'mp4',
        'outtmpl': 'downloads/%(id)s.%(ext)s', # डाउनलोड फोल्डर में सेव होगा
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            # वीडियो की जानकारी (जैसे कैप्शन) निकालना
            info_dict = ydl.extract_info(url, download=True)
            video_title = info_dict.get('description', info_dict.get('title', ''))
            
            # डाउनलोड की गई फाइल का पाथ खोजना
            video_id = info_dict.get('id')
            search_path = f"downloads/{video_id}.*"
            files = glob.glob(search_path)

            if files:
                filepath = files[0]
                # वीडियो को कैप्शन के साथ भेजना
                with open(filepath, 'rb') as video:
                    bot.send_video(
                        chat_id=message.chat.id, 
                        video=video, 
                        caption=video_title if video_title else "Downloaded via Bot",
                        reply_to_message_id=message.message_id
                    )
                
                # भेजने के बाद फाइल डिलीट करना ताकि सर्वर की मेमोरी न भरे
                os.remove(filepath)
                bot.delete_message(message.chat.id, status_msg.message_id)
            else:
                bot.edit_message_text("❌ वीडियो फाइल नहीं मिल सकी। कृपया दोबारा प्रयास करें।", message.chat.id, status_msg.message_id)

    except Exception as e:
        print(f"Error: {e}")
        bot.edit_message_text("❌ डाउनलोड करने में कोई समस्या आई। लिंक सही है या नहीं, यह जांचें या बॉट को दोबारा रिस्टार्ट करें।", message.chat.id, status_msg.message_id)

# बॉट और वेब सर्वर को एक साथ शुरू करना
if __name__ == "__main__":
    # Flask को अलग थ्रेड में चलाएं ताकि Render का पोर्ट चालू रहे
    t = Thread(target=run_flask)
    t.start()
    
    print("Bot is polling...")
    # एरर आने पर बॉट बंद न हो, इसलिए infinity_polling का उपयोग किया है
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
          
