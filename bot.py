import sqlite3
import os
import csv
from io import StringIO
import string

from telegram import ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters
)

TOKEN = os.getenv("TOKEN")

PAGE_SIZE = 10

conn = sqlite3.connect("repertorio.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS brani (
id INTEGER PRIMARY KEY AUTOINCREMENT,
titolo TEXT,
autore TEXT,
copie INTEGER
)
""")

cursor.execute(
    "CREATE INDEX IF NOT EXISTS idx_titolo ON brani(titolo)"
)

conn.commit()

menu = [
["📚 Repertorio", "➕ Aggiungi"],
["🔎 Filtri", "📥 Importa CSV"],
["📊 Statistiche", "ℹ️ Info"]
]

reply_markup = ReplyKeyboardMarkup(menu, resize_keyboard=True)

# -----------------------
# PAGINAZIONE
# -----------------------

def mostra_pagina(update, context, filtro=None, valore=None):

    pagina = context.user_data.get("pagina", 0)
    offset = pagina * PAGE_SIZE

    query = "SELECT titolo, autore, copie FROM brani"
    params = []

    if filtro == "iniziale":
        query += " WHERE titolo LIKE ?"
        params.append(valore + "%")

    if filtro == "autore":
        query += " WHERE autore LIKE ?"
        params.append("%" + valore + "%")

    query += " ORDER BY titolo LIMIT ? OFFSET ?"
    params.extend([PAGE_SIZE, offset])

    cursor.execute(query, params)
    brani = cursor.fetchall()

    if not brani:
        update.message.reply_text("Nessun risultato")
        return

    msg = "\n".join(
        f"{b[0]} - {b[1]} | copie: {b[2]}" for b in brani
    )

    nav = []
    if pagina > 0:
        nav.append("⬅️")
    if len(brani) == PAGE_SIZE:
        nav.append("➡️")

    keyboard = ReplyKeyboardMarkup([nav] + menu, resize_keyboard=True)

    update.message.reply_text(msg, reply_markup=keyboard)

# -----------------------
# MENU
# -----------------------

async def menu_handler(update, context):

    text = update.message.text

    if text == "📚 Repertorio":
        context.user_data["pagina"] = 0
        context.user_data["filtro"] = None
        mostra_pagina(update, context)

    elif text == "➡️":
        context.user_data["pagina"] += 1
        mostra_pagina(update, context,
                      context.user_data.get("filtro"),
                      context.user_data.get("valore"))

    elif text == "⬅️":
        context.user_data["pagina"] = max(0, context.user_data["pagina"] - 1)
        mostra_pagina(update, context,
                      context.user_data.get("filtro"),
                      context.user_data.get("valore"))

    elif text == "🔎 Filtri":

        tastiera = [["Autore", "Iniziale"]]
        await update.message.reply_text(
            "Scegli filtro",
            reply_markup=ReplyKeyboardMarkup(tastiera, resize_keyboard=True)
        )

    elif text == "Iniziale":

        lettere = list(string.ascii_uppercase)
        rows = [lettere[i:i+6] for i in range(0, 26, 6)]

        await update.message.reply_text(
            "Scegli lettera",
            reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True)
        )

        context.user_data["filtro"] = "iniziale"

    elif text == "Autore":

        context.user_data["filtro"] = "autore"

        await update.message.reply_text("Scrivi autore")

    elif len(text) == 1 and text.isalpha():

        context.user_data["valore"] = text
        context.user_data["pagina"] = 0

        mostra_pagina(update, context, "iniziale", text)

    elif context.user_data.get("filtro") == "autore":

        context.user_data["valore"] = text
        context.user_data["pagina"] = 0

        mostra_pagina(update, context, "autore", text)

    elif text == "📊 Statistiche":

        cursor.execute("SELECT COUNT(*) FROM brani")
        totale = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(copie) FROM brani")
        copie = cursor.fetchone()[0] or 0

        await update.message.reply_text(
            f"Brani: {totale}\nCopie: {copie}"
        )

    elif text == "ℹ️ Info":

        await update.message.reply_text(
            "Scrivi titolo o autore per cercare.\nUsa i filtri per navigare."
        )

# -----------------------
# RICERCA INTELLIGENTE
# -----------------------

async def ricerca(update, context):

    text = update.message.text

    if text in ["📚 Repertorio", "🔎 Filtri", "📥 Importa CSV"]:
        return

    cursor.execute(
        """SELECT titolo, autore, copie FROM brani
        WHERE titolo LIKE ? OR autore LIKE ?
        ORDER BY titolo""",
        ('%' + text + '%', '%' + text + '%')
    )

    risultati = cursor.fetchall()

    if risultati:

        msg = "\n".join(
            f"{r[0]} - {r[1]} | copie: {r[2]}"
            for r in risultati
        )

        await update.message.reply_text(msg)

# -----------------------
# BOT
# -----------------------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT, menu_handler))
app.add_handler(MessageHandler(filters.TEXT, ricerca))

print("Bot con filtri avviato")

app.run_polling()
