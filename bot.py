import sqlite3
import os
import csv
from io import StringIO

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
# CONFIG
# -----------------------

PAGE_SIZE = 10

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
copie INTEGER
)
""")

cursor.execute(
    "CREATE INDEX IF NOT EXISTS idx_titolo ON brani(titolo)"
)

conn.commit()

# -----------------------
# MENU
# -----------------------

menu = [
["📚 Repertorio", "➕ Aggiungi"],
["✏️ Modifica copie", "🗑 Elimina brano"],
["📥 Importa CSV", "📊 Statistiche"],
["ℹ️ Info"]
]

reply_markup = ReplyKeyboardMarkup(menu, resize_keyboard=True)

# -----------------------
# STATI
# -----------------------

TITOLO, AUTORE, COPIE = range(3)
MOD_TITOLO, MOD_NUM = range(3,5)
DEL_BRANO = 5

attesa_csv = {}

# -----------------------
# PAGINAZIONE
# -----------------------

def mostra_pagina(update, context):

    pagina = context.user_data.get("pagina", 0)

    offset = pagina * PAGE_SIZE

    cursor.execute(
        "SELECT titolo, autore, copie FROM brani ORDER BY titolo LIMIT ? OFFSET ?",
        (PAGE_SIZE, offset)
    )

    brani = cursor.fetchall()

    if not brani:
        update.message.reply_text("Nessun brano")
        return

    msg = ""

    for b in brani:
        msg += f"{b[0]} - {b[1]} | copie: {b[2]}\n"

    tastiera = []

    nav = []
    if pagina > 0:
        nav.append("⬅️ Indietro")

    if len(brani) == PAGE_SIZE:
        nav.append("➡️ Avanti")

    if nav:
        tastiera.append(nav)

    keyboard = ReplyKeyboardMarkup(
        tastiera + menu,
        resize_keyboard=True
    )

    update.message.reply_text(msg, reply_markup=keyboard)

# -----------------------
# START
# -----------------------

async def start(update, context):

    await update.message.reply_text(
        "Bot repertorio del coro",
        reply_markup=reply_markup
    )

# -----------------------
# MENU
# -----------------------

async def menu_handler(update, context):

    text = update.message.text

    # PAGINAZIONE
    if text == "📚 Repertorio":
        context.user_data["pagina"] = 0
        mostra_pagina(update, context)
        return

    elif text == "➡️ Avanti":
        context.user_data["pagina"] += 1
        mostra_pagina(update, context)
        return

    elif text == "⬅️ Indietro":
        context.user_data["pagina"] = max(0, context.user_data["pagina"] - 1)
        mostra_pagina(update, context)
        return

    elif text == "📊 Statistiche":

        cursor.execute("SELECT COUNT(*) FROM brani")
        totale = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(copie) FROM brani")
        copie = cursor.fetchone()[0] or 0

        await update.message.reply_text(
            f"Brani totali: {totale}\nCopie spartiti: {copie}"
        )

    elif text == "📥 Importa CSV":

        attesa_csv[update.effective_user.id] = True

        await update.message.reply_text(
            "Invia il file CSV con formato:\n"
            "titolo,autore,copie"
        )

    elif text == "ℹ️ Info":

        await update.message.reply_text(
            "Scrivi il titolo o autore per cercare.\n"
            "Usa il menu per gestire il repertorio."
        )

# -----------------------
# RICERCA INTELLIGENTE
# -----------------------

async def ricerca(update, context):

    text = update.message.text

    if text.startswith("📚") or text.startswith("➕") or text.startswith("✏️") \
       or text.startswith("🗑") or text.startswith("📥") \
       or text.startswith("📊") or text.startswith("ℹ️") \
       or text.startswith("⬅️") or text.startswith("➡️"):
        return

    cursor.execute(
        """SELECT titolo, autore, copie FROM brani
        WHERE titolo LIKE ? OR autore LIKE ?
        ORDER BY titolo""",
        ('%' + text + '%', '%' + text + '%')
    )

    risultati = cursor.fetchall()

    if risultati:

        msg = ""
        for r in risultati:
            msg += f"{r[0]} - {r[1]} | copie: {r[2]}\n"

        await update.message.reply_text(msg)

# -----------------------
# IMPORT CSV
# -----------------------

async def importa_csv(update, context):

    user = update.effective_user.id

    if user not in attesa_csv:
        return

    file = await update.message.document.get_file()
    contenuto = await file.download_as_bytearray()

    testo = contenuto.decode("utf-8", errors="ignore")

    reader = csv.DictReader(
        StringIO(testo),
        delimiter=";" if ";" in testo else ","
    )

    count = 0

    for row in reader:
        try:
            copie = int(row["copie"])
        except:
            continue

        cursor.execute(
            "INSERT INTO brani (titolo, autore, copie) VALUES (?, ?, ?)",
            (row["titolo"], row["autore"], copie)
        )

        count += 1

    conn.commit()
    attesa_csv.pop(user)

    await update.message.reply_text(f"Importati {count} brani")

# -----------------------
# AGGIUNTA BRANO
# -----------------------

async def aggiungi(update, context):
    await update.message.reply_text("Titolo?")
    return TITOLO

async def titolo(update, context):
    context.user_data["titolo"] = update.message.text
    await update.message.reply_text("Autore?")
    return AUTORE

async def autore(update, context):
    context.user_data["autore"] = update.message.text
    await update.message.reply_text("Copie?")
    return COPIE

async def copie(update, context):

    if not update.message.text.isdigit():
        await update.message.reply_text("Numero non valido")
        return COPIE

    cursor.execute(
        "INSERT INTO brani VALUES (NULL, ?, ?, ?)",
        (context.user_data["titolo"], context.user_data["autore"], int(update.message.text))
    )

    conn.commit()

    await update.message.reply_text("Salvato", reply_markup=reply_markup)

    return ConversationHandler.END

# -----------------------
# BOT
# -----------------------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

app.add_handler(MessageHandler(filters.Document.ALL, importa_csv))
app.add_handler(MessageHandler(filters.TEXT, menu_handler))
app.add_handler(MessageHandler(filters.TEXT, ricerca))

print("Bot avviato")

app.run_polling()
