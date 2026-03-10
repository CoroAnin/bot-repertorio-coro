import sqlite3
import os

from telegram import ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters
)

TOKEN = os.getenv("TOKEN")

# -----------------------
# DATABASE
# -----------------------

conn = sqlite3.connect("repertorio.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS brani (
id INTEGER PRIMARY KEY AUTOINCREMENT,
titolo TEXT,
autore TEXT,
voci TEXT,
copie INTEGER,
note TEXT,
link TEXT
)
""")

conn.commit()

# -----------------------
# MENU
# -----------------------

menu = [
["📚 Repertorio", "🔎 Cerca"],
["➕ Aggiungi", "📊 Statistiche"]
]

reply_markup = ReplyKeyboardMarkup(menu, resize_keyboard=True)

# -----------------------
# STATI CONVERSAZIONE
# -----------------------

TITOLO, AUTORE, VOCI, COPIE = range(4)

# -----------------------
# START
# -----------------------

async def start(update, context):

    await update.message.reply_text(
        "Bot repertorio del coro",
        reply_markup=reply_markup
    )

# -----------------------
# MENU PRINCIPALE
# -----------------------

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

        if copie is None:
            copie = 0

        await update.message.reply_text(
            f"Brani totali: {totale}\nCopie spartiti: {copie}"
        )

    elif text == "🔎 Cerca":

        await update.message.reply_text(
            "Scrivi una parola del titolo"
        )

# -----------------------
# RICERCA BRANI
# -----------------------

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

# -----------------------
# INSERIMENTO BRANO
# -----------------------

async def aggiungi(update, context):

    await update.message.reply_text("Titolo del brano?")
    return TITOLO


async def titolo(update, context):

    context.user_data["titolo"] = update.message.text
    await update.message.reply_text("Autore?")
    return AUTORE


async def autore(update, context):

    context.user_data["autore"] = update.message.text
    await update.message.reply_text("Tipo voci (SATB / SSA / TTBB)?")
    return VOCI


async def voci(update, context):

    context.user_data["voci"] = update.message.text
    await update.message.reply_text("Numero copie?")
    return COPIE


async def copie(update, context):

    testo = update.message.text

    if not testo.isdigit():

        await update.message.reply_text(
            "Il numero copie deve essere un numero. Inserisci di nuovo."
        )

        return COPIE

    copie = int(testo)

    titolo = context.user_data["titolo"]
    autore = context.user_data["autore"]
    voci = context.user_data["voci"]

    cursor.execute("""
    INSERT INTO brani
    (titolo, autore, voci, copie)
    VALUES (?, ?, ?, ?)
    """, (titolo, autore, voci, copie))

    conn.commit()

    await update.message.reply_text("Brano salvato!")

    return ConversationHandler.END


async def annulla(update, context):

    await update.message.reply_text("Inserimento annullato")
    return ConversationHandler.END

# -----------------------
# BOT
# -----------------------

app = ApplicationBuilder().token(TOKEN).build()

conv_handler = ConversationHandler(

    entry_points=[MessageHandler(filters.Regex("➕ Aggiungi"), aggiungi)],

    states={

        TITOLO: [MessageHandler(filters.TEXT & ~filters.COMMAND, titolo)],
        AUTORE: [MessageHandler(filters.TEXT & ~filters.COMMAND, autore)],
        VOCI: [MessageHandler(filters.TEXT & ~filters.COMMAND, voci)],
        COPIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, copie)],

    },

    fallbacks=[CommandHandler("annulla", annulla)]

)

app.add_handler(CommandHandler("start", start))
app.add_handler(conv_handler)
app.add_handler(MessageHandler(filters.TEXT, menu_handler))
app.add_handler(MessageHandler(filters.TEXT, ricerca))

print("Bot avviato")

app.run_polling()
