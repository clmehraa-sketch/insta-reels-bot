import os
import time
import threading
from flask import Flask
import telebot
import yt_dlp

# Render के Environment Variable से बॉट टोकन लें
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
bot = telebot.TeleBot(BOT_TOKEN)

# 1. Flask वेब सर्वर (Cron-job से बॉट को 24x7 जगाए रखने के लिए)
app = Flask(__name__)

@app.route('/')
def home():
    return "Instagram Reel Bot is Running Alive!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# 2. Instagram Reel डाउनलोड करने का फंक्शन
def download_instagram_reel(url, unique_id):
    output_template = f"reel_{unique_id}.%(ext)s"
    
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }

    # अगर आपने ब्लॉक से बचने के लिए cookies.txt डाली है, तो यह अपने आप उसे इस्तेमाल करेगा
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        caption = info.get('description') or "कोई कैप्शन उपलब्ध नहीं है।"
        return filename, caption

# 3. Telegram कमांड और लिंक हैंडलर
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "नमस्ते! मुझे किसी भी Instagram Reel का लिंक भेजें, मैं आपको वीडियो और उसका पूरा कैप्शन भेज दूंगा।"
    )

@bot.message_handler(func=lambda message: True)
def handle_reel_link(message):
    url = message.text.strip()
    
    if "instagram.com/" not in url:
        bot.reply_to(message, "कृपया एक सही Instagram Reel लिंक भेजें।")
        return

    status_msg = bot.reply_to(message, "⏳ रील डाउनलोड हो रही है, कृपया प्रतीक्षा करें...")
    unique_id = f"{message.chat.id}_{message.message_id}"
    video_path = None

    try:
        video_path, caption = download_instagram_reel(url, unique_id)

        # टेलीग्राम वीडियो कैप्शन की लिमिट 1024 अक्षर होती है
        # अगर कैप्शन छोटा है तो वीडियो के साथ भेजें, बड़ा है तो अलग मैसेज में भेजें
        with open(video_path, 'rb') as video_file:
            if len(caption) <= 1000:
                bot.send_video(
                    message.chat.id, 
                    video_file, 
                    caption=caption, 
                    reply_to_message_id=message.message_id
                )
            else:
                bot.send_video(
                    message.chat.id, 
                    video_file, 
                    caption="✅ लीजिए आपकी रील! (कैप्शन बड़ा होने के कारण नीचे अलग मैसेज में दिया गया है)",
                    reply_to_message_id=message.message_id
                )
                # 4096 अक्षर की लिमिट के हिसाब से पूरा कैप्शन भेजें
                bot.send_message(message.chat.id, caption[:4090], reply_to_message_id=message.message_id)

        bot.delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(
            f"❌ डाउनलोड करने में समस्या आई। सुनिश्चित करें कि रील पब्लिक अकाउंट की है।\n\nतकनीकी कारण: {str(e)[:150]}",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )
    
    finally:
        # सर्वर की मेमोरी फुल होने से बचाने के लिए फाइल तुरंत डिलीट करें
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                pass

# 4. बॉट और सर्वर को एक साथ शुरू करें (ऑटो-रीस्टार्ट के साथ)
if __name__ == "__main__":
    # बैकग्राउंड में Flask वेब सर्वर चलाएं
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    # पुराने वेबहुक हटाएं ताकि 409 Conflict एरर न आए
    bot.remove_webhook()
    time.sleep(1)
    
    print("Bot is polling...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
