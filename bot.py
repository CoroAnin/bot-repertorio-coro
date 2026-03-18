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
TIPOLOGIE = ["Natale", "Contemporaneo", "Popolare", "Sacro"]

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

# aggiunta tipologia se non esiste
try:
    cursor.execute("ALTER TABLE brani ADD COLUMN tipologia TEXT")
except:
    pass

cursor.execute("CREATE INDEX IF NOT EXISTS idx_titolo ON brani(titolo)")
conn.commit()

# -----------------------
# MENU
# -----------------------

menu = [
["📚 Repertorio", "➕ Aggiungi"],
["🔎 Filtri", "📥 Importa CSV"],
["📊 Statistiche", "ℹ️ Info"]
]

reply_markup = ReplyKeyboardMarkup(menu, resize_keyboard=True)

# -----------------------
# STATI
# -----------------------

TITOLO, AUTORE, COPIE, TIPOLOGIA = range(4)

attesa_csv = {}

# -----------------------
# PAGINAZIONE
# -----------------------

def mostra_pagina(update, context):

    pagina = context.user_data.get("pagina", 0)
    offset = pagina * PAGE_SIZE

    query = "SELECT titolo, autore, copie FROM brani"
    params = []

    filtro = context.user_data.get("filtro")
    valore = context.user_data.get("valore")

    if filtro == "iniziale":
        query += " WHERE titolo LIKE ?"
        params.append(valore + "%")

    elif filtro == "tipologia":
        query += " WHERE tipologia = ?"
        params.append(valore)

    query += " ORDER BY titolo LIMIT ? OFFSET ?"
    params.extend([PAGE_SIZE, offset])

    cursor.execute(query, params)
    brani = cursor.fetchall()

    if not brani:
        update.message.reply_text("Nessun risultato")
        return

    msg = "\n".join(
        f"{b[0]} - {b[1]} | copie: {b[2]}"
        for b in brani
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
        mostra_pagina(update, context)

    elif text == "⬅️":
        context.user_data["pagina"] = max(0, context.user_data["pagina"] - 1)
        mostra_pagina(update, context)

    elif text == "🔎 Filtri":

        tastiera = [["Tipologia", "Iniziale"]]
        await update.message.reply_text(
            "Scegli filtro",
            reply_markup=ReplyKeyboardMarkup(tastiera, resize_keyboard=True)
        )

    elif text == "Tipologia":

        rows = [TIPOLOGIE[i:i+2] for i in range(0, len(TIPOLOGIE), 2)]

        await update.message.reply_text(
            "Scegli tipologia",
            reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True)
        )

        context.user_data["filtro"] = "tipologia"

    elif text in TIPOLOGIE:

        context.user_data["valore"] = text
        context.user_data["pagina"] = 0
        mostra_pagina(update, context)

    elif text == "Iniziale":

        lettere = list(string.ascii_uppercase)
        rows = [lettere[i:i+6] for i in range(0, 26, 6)]

        await update.message.reply_text(
            "Scegli lettera",
            reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True)
        )

        context.user_data["filtro"] = "iniziale"

    elif len(text) == 1 and text.isalpha():

        context.user_data["valore"] = text
        context.user_data["pagina"] = 0
        mostra_pagina(update, context)

    elif text == "📊 Statistiche":

        cursor.execute("SELECT COUNT(*) FROM brani")
        totale = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(copie) FROM brani")
        copie = cursor.fetchone()[0] or 0

        await update.message.reply_text(
            f"Brani: {totale}\nCopie: {copie}"
        )

    elif text == "📥 Importa CSV":

        attesa_csv[update.effective_user.id] = True
        await update.message.reply_text("Invia file CSV")

    elif text == "ℹ️ Info":

        await update.message.reply_text(
            "Scrivi titolo o autore per cercare.\nUsa i filtri."
        )

# -----------------------
# RICERCA
# -----------------------

async def ricerca(update, context):

    text = update.message.text

    if text in sum(menu, []) or text in ["⬅️", "➡️"]:
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
            "INSERT INTO brani (titolo, autore, copie, tipologia) VALUES (?, ?, ?, ?)",
            (row["titolo"], row["autore"], copie, row.get("tipologia"))
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

    context.user_data["copie"] = int(update.message.text)

    rows = [TIPOLOGIE[i:i+2] for i in range(0, len(TIPOLOGIE), 2)]

    await update.message.reply_text(
        "Scegli tipologia",
        reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True)
    )

    return TIPOLOGIA

async def tipologia(update, context):

    if update.message.text not in TIPOLOGIE:
        await update.message.reply_text("Seleziona una tipologia valida")
        return TIPOLOGIA

    cursor.execute(
        "INSERT INTO brani (titolo, autore, copie, tipologia) VALUES (?, ?, ?, ?)",
        (
            context.user_data["titolo"],
            context.user_data["autore"],
            context.user_data["copie"],
            update.message.text
        )
    )

    conn.commit()

    await update.message.reply_text(
        "Brano salvato!",
        reply_markup=reply_markup
    )

    return ConversationHandler.END

# -----------------------
# BOT
# -----------------------

app = ApplicationBuilder().token(TOKEN).build()

conv_add = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Aggiungi$"), aggiungi)],
    states={
        TITOLO: [MessageHandler(filters.TEXT & ~filters.COMMAND, titolo)],
        AUTORE: [MessageHandler(filters.TEXT & ~filters.COMMAND, autore)],
        COPIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, copie)],
        TIPOLOGIA: [MessageHandler(filters.Regex(f"^({'|'.join(TIPOLOGIE)})$"), tipologia)],
    },
    fallbacks=[]
)

# ordine corretto
app.add_handler(conv_add, group=1)
app.add_handler(MessageHandler(filters.Document.ALL, importa_csv), group=2)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler), group=3)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ricerca), group=4)

app.add_handler(CommandHandler("start", start))

print("Bot stabile avviato")

app.run_polling()
