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
["✏️ Modifica copie", "🗑 Elimina brano"],
["🔎 Filtri", "📥 Importa CSV"],
["📊 Statistiche", "ℹ️ Info"]
]

reply_markup = ReplyKeyboardMarkup(menu, resize_keyboard=True)
annulla_markup = ReplyKeyboardMarkup([["❌ Annulla"]], resize_keyboard=True)

# -----------------------
# STATI
# -----------------------

TITOLO, AUTORE, COPIE, TIPOLOGIA = range(4)
MOD_TITOLO, MOD_NUM = range(4,6)
DEL_BRANO = 6

attesa_csv = {}

# -----------------------
# ANNULLA UNIVERSALE
# -----------------------

async def annulla(update, context):
    context.user_data.clear()
    await update.message.reply_text(
        "Operazione annullata",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

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

    # ANNULLA globale
    if text == "❌ Annulla":
        return await annulla(update, context)

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

        await update.message.reply_text(
            "Scegli filtro",
            reply_markup=ReplyKeyboardMarkup(
                [["Tipologia", "Iniziale"], ["❌ Annulla"]],
                resize_keyboard=True
            )
        )

    elif text == "Tipologia":

        rows = [TIPOLOGIE[i:i+2] for i in range(0, len(TIPOLOGIE), 2)]
        rows.append(["❌ Annulla"])

        await update.message.reply_text(
            "Scegli tipologia",
            reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True)
        )

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
        rows.append(["❌ Annulla"])

        await update.message.reply_text(
            "Scegli lettera",
            reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True)
        )

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
        await update.message.reply_text("Invia file CSV", reply_markup=annulla_markup)

    elif text == "ℹ️ Info":

        await update.message.reply_text(
            "Scrivi titolo/autore per cercare.\nUsa i menu per gestire."
        )

# -----------------------
# RICERCA
# -----------------------

async def ricerca(update, context):

    text = update.message.text

    if text in sum(menu, []) or text == "❌ Annulla" or text in TIPOLOGIE:
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

    await update.message.reply_text(f"Importati {count} brani", reply_markup=reply_markup)

# -----------------------
# AGGIUNTA
# -----------------------

async def aggiungi(update, context):
    await update.message.reply_text("Titolo?", reply_markup=annulla_markup)
    return TITOLO

async def titolo(update, context):
    context.user_data["titolo"] = update.message.text
    await update.message.reply_text("Autore?", reply_markup=annulla_markup)
    return AUTORE

async def autore(update, context):
    context.user_data["autore"] = update.message.text
    await update.message.reply_text("Copie?", reply_markup=annulla_markup)
    return COPIE

async def copie(update, context):

    if not update.message.text.isdigit():
        await update.message.reply_text("Numero non valido")
        return COPIE

    context.user_data["copie"] = int(update.message.text)

    rows = [TIPOLOGIE[i:i+2] for i in range(0, len(TIPOLOGIE), 2)]
    rows.append(["❌ Annulla"])

    await update.message.reply_text(
        "Scegli tipologia",
        reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True)
    )

    return TIPOLOGIA

async def tipologia(update, context):

    if update.message.text not in TIPOLOGIE:
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

    lista.append(["❌ Annulla"])

    tastiera = ReplyKeyboardMarkup(lista, resize_keyboard=True)

    await update.message.reply_text("Scegli il brano", reply_markup=tastiera)

    return MOD_TITOLO


async def mod_titolo(update, context):

    if update.message.text == "❌ Annulla":
        return await annulla(update, context)

    context.user_data["titolo_mod"] = update.message.text

    await update.message.reply_text(
        "Quante copie aggiungere o togliere?",
        reply_markup=annulla_markup
    )

    return MOD_NUM


async def mod_num(update, context):

    if update.message.text == "❌ Annulla":
        return await annulla(update, context)

    try:
        delta = int(update.message.text)
    except:
        await update.message.reply_text("Numero non valido")
        return MOD_NUM

    titolo = context.user_data["titolo_mod"]

    cursor.execute("SELECT copie FROM brani WHERE titolo=?", (titolo,))
    copie_attuali = cursor.fetchone()[0]

    nuove = max(0, copie_attuali + delta)

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
# ELIMINA
# -----------------------

async def elimina(update, context):

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

    lista.append(["❌ Annulla"])

    tastiera = ReplyKeyboardMarkup(lista, resize_keyboard=True)

    await update.message.reply_text(
        "Seleziona il brano da eliminare",
        reply_markup=tastiera
    )

    return DEL_BRANO


async def elimina_brano(update, context):

    if update.message.text == "❌ Annulla":
        return await annulla(update, context)

    titolo = update.message.text

    cursor.execute("DELETE FROM brani WHERE titolo=?", (titolo,))
    conn.commit()

    await update.message.reply_text(
        f"Brano eliminato: {titolo}",
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
        TIPOLOGIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, tipologia)],
    },
    fallbacks=[MessageHandler(filters.Regex("^❌ Annulla$"), annulla)]
)

conv_mod = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^✏️ Modifica copie$"), modifica)],
    states={
        MOD_TITOLO: [MessageHandler(filters.TEXT & ~filters.COMMAND, mod_titolo)],
        MOD_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, mod_num)],
    },
    fallbacks=[MessageHandler(filters.Regex("^❌ Annulla$"), annulla)]
)

conv_del = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^🗑 Elimina brano$"), elimina)],
    states={
        DEL_BRANO: [MessageHandler(filters.TEXT & ~filters.COMMAND, elimina_brano)],
    },
    fallbacks=[MessageHandler(filters.Regex("^❌ Annulla$"), annulla)]
)

app.add_handler(CommandHandler("start", start), group=0)
app.add_handler(conv_add, group=1)
app.add_handler(conv_mod, group=1)
app.add_handler(conv_del, group=1)
app.add_handler(MessageHandler(filters.Document.ALL, importa_csv), group=2)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler), group=3)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ricerca), group=4)

print("Bot avviato")

app.run_polling()
