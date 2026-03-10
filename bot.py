import sqlite3
from telegram import ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

import os
TOKEN = os.getenv("TOKEN")

from telegram.ext import ConversationHandler
TITOLO, AUTORE, VOCI, COPIE = range(6)
async def aggiungi(update, context):

    await update.message.reply_text("Titolo del brano?")
    return TITOLO

async def titolo(update, context):

    context.user_data["titolo"] = update.message.text
    await update.message.reply_text("Autore?")
    return AUTORE

async def autore(update, context):

    context.user_data["autore"] = update.message.text
    await update.message.reply_text("Lingua?")
    return LINGUA

async def voci(update, context):

    context.user_data["voci"] = update.message.text
    await update.message.reply_text("Tonalità?")
    return TONALITA

async def copie(update, context):

    copie = update.message.text

    titolo = context.user_data["titolo"]
    autore = context.user_data["autore"]
    lingua = context.user_data["lingua"]
    voci = context.user_data["voci"]
    tonalita = context.user_data["tonalita"]

    cursor.execute("""
    INSERT INTO brani
    (titolo, autore, lingua, voci, tonalita, copie)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (titolo, autore, lingua, voci, tonalita, copie))

    conn.commit()

    await update.message.reply_text("Brano salvato!")

    return ConversationHandler.END

async def annulla(update, context):

    await update.message.reply_text("Inserimento annullato")
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("➕ Aggiungi"), aggiungi)],

    states={

        TITOLO: [MessageHandler(filters.TEXT & ~filters.COMMAND, titolo)],
        AUTORE: [MessageHandler(filters.TEXT & ~filters.COMMAND, autore)],
        LINGUA: [MessageHandler(filters.TEXT & ~filters.COMMAND, lingua)],
        VOCI: [MessageHandler(filters.TEXT & ~filters.COMMAND, voci)],
        TONALITA: [MessageHandler(filters.TEXT & ~filters.COMMAND, tonalita)],
        COPIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, copie)],

    },

    fallbacks=[CommandHandler("annulla", annulla)]
)

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
app.add_handler(conv_handler)


app.run_polling()

