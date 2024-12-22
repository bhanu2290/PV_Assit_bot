import os
import logging
import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
load_dotenv("config.env")

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Logging Configuration
logging.basicConfig(
    filename="logs/bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Load Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Use config.env or set as an environment variable

# Database Connection (Ensure database folder exists)
db_path = os.path.join(os.getcwd(), 'db', 'tasks.db')
os.makedirs(os.path.dirname(db_path), exist_ok=True)

# Connect to SQLite database (single connection)
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

# Create tasks table if not exists
cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    task TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
conn.commit()

# Scheduler for Reminders
scheduler = BackgroundScheduler()
scheduler.start()

# Admin User IDs (Replace with actual Telegram user IDs)
ADMIN_IDS = [6884152393]  # Example numerical IDs for Telegram users


# Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to Persist Ventures Bot! Use /help for commands.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
Available Commands:
/start - Welcome Message
/help - Show Commands
/addtask <task> - Add a task
/listtasks - List all tasks
/upload - Upload a file
/schedule <time> <reminder> - Schedule a reminder (Admin Only)
    """
    await update.message.reply_text(help_text)

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = " ".join(context.args)
    if task:
        cursor.execute("INSERT INTO tasks (user_id, task) VALUES (?, ?)", (update.message.chat_id, task))
        conn.commit()
        await update.message.reply_text(f"Task saved: {task}")
    else:
        await update.message.reply_text("Please provide a task. Example: /addtask Submit report.")

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT task FROM tasks WHERE user_id = ?", (update.message.chat_id,))
    tasks = cursor.fetchall()
    if tasks:
        tasks_list = "\n".join([f"- {task[0]}" for task in tasks])
        await update.message.reply_text(f"Your tasks:\n{tasks_list}")
    else:
        await update.message.reply_text("No tasks found. Add one with /addtask.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file = await context.bot.get_file(document.file_id)
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{document.file_name}"
    await file.download_to_drive(file_path)
    await update.message.reply_text(f"File {document.file_name} uploaded successfully!")

async def admin_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    try:
        time, reminder = context.args[0], " ".join(context.args[1:])
        scheduler.add_job(
            func=send_reminder,
            trigger="date",
            run_date=time,
            args=[context.bot, update.message.chat_id, reminder],
        )
        await update.message.reply_text(f"Reminder scheduled at {time}: {reminder}")
    except Exception as e:
        logging.error(e)
        await update.message.reply_text("Error scheduling reminder. Use format: /schedule <YYYY-MM-DD HH:MM> <reminder>")

async def send_reminder(bot, chat_id, reminder):
    await bot.send_message(chat_id=chat_id, text=f"Reminder: {reminder}")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "1":
        await query.edit_message_text("Option 1 selected.")
    elif query.data == "2":
        await query.edit_message_text("Option 2 selected.")
    else:
        await query.edit_message_text("Action canceled.")

# Application Setup
print(f"Bot Token: {BOT_TOKEN}") 
app = ApplicationBuilder().token(BOT_TOKEN).build()

# Add handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("addtask", add_task))
app.add_handler(CommandHandler("listtasks", list_tasks))
app.add_handler(CommandHandler("schedule", admin_schedule))
app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
app.add_handler(CallbackQueryHandler(button_click))

# Start the bot
if __name__ == "__main__":
    logging.info("Bot started.")
    app.run_polling()
