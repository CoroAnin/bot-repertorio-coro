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

conn.commit()

# -----------------------
# MENU
# -----------------------

menu = [
["📚 Repertorio", "🔎 Cerca titolo"],
["👤 Cerca autore", "➕ Aggiungi"],
["✏️ Modifica copie", "📥 Importa CSV"],
["📊 Statistiche", "ℹ️ Info"]
]

reply_markup = ReplyKeyboardMarkup(menu, resize_keyboard=True)

# -----------------------
# STATI
# -----------------------

TITOLO, AUTORE, COPIE = range(3)
MOD_TITOLO, MOD_NUM = range(3,5)

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

        cursor.execute("SELECT titolo, autore, copie FROM brani ORDER BY titolo")
        brani = cursor.fetchall()

        if not brani:
            await update.message.reply_text("Archivio vuoto")
            return

        msg = ""

        for b in brani:
            msg += f"{b[0]} - {b[1]} | copie: {b[2]}\n"

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

    elif text == "🔎 Cerca titolo":

        context.user_data["ricerca"] = "titolo"
        await update.message.reply_text("Scrivi il titolo")

    elif text == "👤 Cerca autore":

        context.user_data["ricerca"] = "autore"
        await update.message.reply_text("Scrivi l'autore")

    elif text == "📥 Importa CSV":

        attesa_csv[update.effective_user.id] = True

        await update.message.reply_text(
            "Invia il file CSV con formato:\n\n"
            "titolo,autore,copie"
        )

    elif text == "ℹ️ Info":

        msg = """
BOT REPERTORIO CORO

Funzioni principali

📚 Repertorio
Mostra tutti i brani con numero copie.

🔎 Cerca titolo
Trova brani per titolo.

👤 Cerca autore
Trova brani per autore.

➕ Aggiungi
Inserisce un nuovo brano.

✏️ Modifica copie
Aggiorna il numero copie.

📥 Importa CSV
Permette di caricare molti brani da file CSV.

📊 Statistiche
Mostra numero totale brani e copie.
"""

        await update.message.reply_text(msg)

# -----------------------
# RICERCA
# -----------------------

async def ricerca(update, context):

    if "ricerca" not in context.user_data:
        return

    tipo = context.user_data["ricerca"]
    query = update.message.text

    if tipo == "titolo":

        cursor.execute(
            "SELECT titolo, autore, copie FROM brani WHERE titolo LIKE ?",
            ('%' + query + '%',)
        )

    else:

        cursor.execute(
            "SELECT titolo, autore, copie FROM brani WHERE autore LIKE ?",
            ('%' + query + '%',)
        )

    risultati = cursor.fetchall()

    if risultati:

        msg = ""

        for r in risultati:
            msg += f"{r[0]} - {r[1]} | copie: {r[2]}\n"

    else:
        msg = "Nessun risultato"

    await update.message.reply_text(msg)

    context.user_data.pop("ricerca")

# -----------------------
# IMPORT CSV
# -----------------------

async def importa_csv(update, context):

    user = update.effective_user.id

    if user not in attesa_csv:
        return

    file = await update.message.document.get_file()
    contenuto = await file.download_as_bytearray()

    testo = contenuto.decode("utf-8")

    reader = csv.DictReader(StringIO(testo))

    count = 0

    for row in reader:

        titolo = row["titolo"]
        autore = row["autore"]

        try:
            copie = int(row["copie"])
        except:
            continue

        cursor.execute(
            "INSERT INTO brani (titolo, autore, copie) VALUES (?, ?, ?)",
            (titolo, autore, copie)
        )

        count += 1

    conn.commit()

    attesa_csv.pop(user)

    await update.message.reply_text(
        f"Importazione completata: {count} brani caricati."
    )

# -----------------------
# AGGIUNTA BRANO
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
    await update.message.reply_text("Numero copie?")
    return COPIE


async def copie(update, context):

    testo = update.message.text

    if not testo.isdigit():

        await update.message.reply_text("Il numero copie deve essere un numero.")
        return COPIE

    copie = int(testo)

    cursor.execute(
        "INSERT INTO brani (titolo, autore, copie) VALUES (?, ?, ?)",
        (context.user_data["titolo"], context.user_data["autore"], copie)
    )

    conn.commit()

    await update.message.reply_text("Brano salvato!", reply_markup=reply_markup)

    return ConversationHandler.END

# -----------------------
# MODIFICA COPIE
# -----------------------

async def modifica(update, context):

    cursor.execute("SELECT titolo FROM brani ORDER BY titolo")
    brani = cursor.fetchall()

    lista = []
    riga = []

    for b in brani:

        riga.append(b[0])

        if len(riga) == 2:
            lista.append(riga)
            riga = []

    if riga:
        lista.append(riga)

    tastiera = ReplyKeyboardMarkup(lista, resize_keyboard=True)

    await update.message.reply_text(
        "Scegli il brano",
        reply_markup=tastiera
    )

    return MOD_TITOLO


async def mod_titolo(update, context):

    titolo = update.message.text

    context.user_data["titolo_mod"] = titolo

    await update.message.reply_text(
        "Quante copie aggiungere o togliere? (es: 5 oppure -3)"
    )

    return MOD_NUM


async def mod_num(update, context):

    try:
        delta = int(update.message.text)
    except:
        await update.message.reply_text("Inserisci un numero valido")
        return MOD_NUM

    titolo = context.user_data["titolo_mod"]

    cursor.execute(
        "SELECT copie FROM brani WHERE titolo=?",
        (titolo,)
    )

    copie_attuali = cursor.fetchone()[0]

    nuove = copie_attuali + delta

    if nuove < 0:
        nuove = 0

    cursor.execute(
        "UPDATE brani SET copie=? WHERE titolo=?",
        (nuove, titolo)
    )

    conn.commit()

    await update.message.reply_text(
        f"Copie aggiornate: {nuove}",
        reply_markup=reply_markup
    )

    return ConversationHandler.END

# -----------------------
# BOT
# -----------------------

app = ApplicationBuilder().token(TOKEN).build()

conv_add = ConversationHandler(

    entry_points=[MessageHandler(filters.Regex("➕ Aggiungi"), aggiungi)],

    states={
        TITOLO: [MessageHandler(filters.TEXT & ~filters.COMMAND, titolo)],
        AUTORE: [MessageHandler(filters.TEXT & ~filters.COMMAND, autore)],
        COPIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, copie)],
    },

    fallbacks=[]
)

conv_mod = ConversationHandler(

    entry_points=[MessageHandler(filters.Regex("✏️ Modifica copie"), modifica)],

    states={
        MOD_TITOLO: [MessageHandler(filters.TEXT & ~filters.COMMAND, mod_titolo)],
        MOD_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, mod_num)],
    },

    fallbacks=[]
)

app.add_handler(CommandHandler("start", start))

app.add_handler(conv_add)
app.add_handler(conv_mod)

app.add_handler(MessageHandler(filters.Document.ALL, importa_csv))

app.add_handler(MessageHandler(filters.TEXT, menu_handler))
app.add_handler(MessageHandler(filters.TEXT, ricerca))

print("Bot avviato")

app.run_polling()
