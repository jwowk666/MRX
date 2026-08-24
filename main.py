import os
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- 1. خادم Flask مصغر للحفاظ على عمل Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- 2. أوامر البوت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! بوت MRX يعمل الآن بنجاح على Render 🚀")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("قائمة الأوامر:\n/start - تشغيل البوت\n/help - المساعدة")

# --- 3. تشغيل البوت عبر Async Loop لتفادي التعارض ---
async def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("خطأ: لم يتم العثور على BOT_TOKEN!")
        return

    # تشغيل Flask في مسار منفصل
    threading.Thread(target=run_flask, daemon=True).start()

    # بناء البوت
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # بدء البوت بالطريقة المباشرة
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    # إبقاء البوت يعمل باستمرار
    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
