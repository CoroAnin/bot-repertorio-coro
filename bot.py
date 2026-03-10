import sqlite3
from telegram import ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

TOKEN = "8796012899:AAGDbOjUP4Pb08SYf3-p6bl4yZ5208e129E"

conn = sqlite3.connect("repertorio.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS brani (
id INTEGER PRIMARY KEY AUTOINCREMENT,
titolo TEXT,
autore TEXT,
lingua TEXT,
voci TEXT,
tonalita TEXT,
difficolta TEXT,
stagione TEXT,
copie INTEGER,
note TEXT,
link TEXT
)
""")

conn.commit()

menu = [
["📚 Repertorio", "🔎 Cerca"],
["👤 Autore", "🎼 Voci"],
["➕ Aggiungi", "📊 Statistiche"]
]

reply_markup = ReplyKeyboardMarkup(menu, resize_keyboard=True)


async def start(update, context):
    await update.message.reply_text(
        "Bot repertorio coro",
        reply_markup=reply_markup
    )


async def menu_handler(update, context):

    text = update.message.text

    if text == "📚 Repertorio":

        cursor.execute("SELECT titolo, autore FROM brani")
        brani = cursor.fetchall()

        if not brani:
            await update.message.reply_text("Archivio vuoto")
            return

        msg = ""

        for b in brani:
            msg += f"{b[0]} - {b[1]}\n"

        await update.message.reply_text(msg[:4000])

    elif text == "📊 Statistiche":

        cursor.execute("SELECT COUNT(*) FROM brani")
        totale = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(copie) FROM brani")
        copie = cursor.fetchone()[0]

        await update.message.reply_text(
            f"Brani totali: {totale}\nCopie spartiti: {copie}"
        )

    elif text == "🔎 Cerca":

        await update.message.reply_text(
            "Scrivi una parola del titolo"
        )

    elif text == "👤 Autore":

        await update.message.reply_text(
            "Scrivi il nome dell'autore"
        )

    elif text == "🎼 Voci":

        await update.message.reply_text(
            "Scrivi tipo voci (SATB / SSA / TTBB)"
        )


async def ricerca(update, context):

    query = update.message.text

    cursor.execute(
        "SELECT titolo, autore, voci, copie FROM brani WHERE titolo LIKE ?",
        ('%' + query + '%',)
    )

    risultati = cursor.fetchall()

    if risultati:

        msg = ""

        for r in risultati:

            msg += (
                f"TITOLO: {r[0]}\n"
                f"AUTORE: {r[1]}\n"
                f"VOCI: {r[2]}\n"
                f"COPIE: {r[3]}\n\n"
            )

    else:
        msg = "Nessun risultato"

    await update.message.reply_text(msg)


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, menu_handler))

app.run_polling()