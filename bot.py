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

TIPOLOGIE = ["Natale", "Pasqua", "Ordinario", "Concerto"]

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

# aggiunge colonna tipologia se non esiste
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
MOD_TITOLO, MOD_NUM = range(4,6)
DEL_BRANO = 6

attesa_csv = {}

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

    if text == "📚 Repertorio":

        cursor.execute(
            "SELECT titolo, autore, copie, tipologia FROM brani ORDER BY titolo"
        )

        brani = cursor.fetchall()

        if not brani:
            await update.message.reply_text("Archivio vuoto")
            return

        msg = ""
        for b in brani:
            tipo = b[3] if b[3] else "-"
            msg += f"{b[0]} - {b[1]} | copie: {b[2]} | {tipo}\n"

        await update.message.reply_text(msg[:4000])

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

        cursor.execute(
            "SELECT titolo, autore, copie FROM brani WHERE tipologia=? ORDER BY titolo",
            (text,)
        )

        risultati = cursor.fetchall()

        msg = "\n".join(
            f"{r[0]} - {r[1]} | copie: {r[2]}"
            for r in risultati
        )

        await update.message.reply_text(msg or "Nessun risultato")

    elif text == "Iniziale":

        lettere = list(string.ascii_uppercase)
        rows = [lettere[i:i+6] for i in range(0, 26, 6)]

        await update.message.reply_text(
            "Scegli lettera",
            reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True)
        )

        context.user_data["filtro"] = "iniziale"

    elif len(text) == 1 and text.isalpha():

        cursor.execute(
            "SELECT titolo, autore, copie FROM brani WHERE titolo LIKE ? ORDER BY titolo",
            (text + "%",)
        )

        risultati = cursor.fetchall()

        msg = "\n".join(
            f"{r[0]} - {r[1]} | copie: {r[2]}"
            for r in risultati
        )

        await update.message.reply_text(msg or "Nessun risultato")

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

        await update.message.reply_text("Invia file CSV")

    elif text == "ℹ️ Info":

        await update.message.reply_text(
            "Usa il menu oppure scrivi titolo/autore per cercare."
        )

# -----------------------
# RICERCA
# -----------------------

async def ricerca(update, context):

    text = update.message.text

    if text in sum(menu, []) or text in TIPOLOGIE:
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

    await update.message.reply_text("Brano salvato!", reply_markup=reply_markup)

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

# ORDINE CORRETTO
app.add_handler(CommandHandler("start", start), group=0)
app.add_handler(conv_add, group=1)
app.add_handler(MessageHandler(filters.Document.ALL, importa_csv), group=2)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler), group=3)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ricerca), group=4)

print("Bot avviato")

app.run_polling()
