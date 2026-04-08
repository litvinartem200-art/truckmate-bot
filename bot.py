import os, logging, aiohttp, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Данные из Railway
TOKEN = os.environ.get("BOT_TOKEN", "")
ORS_KEY = os.environ.get("ORS_API_KEY", "")

# Средние цены дизеля
DIESEL = {"FR": 1.65, "DE": 1.71, "IT": 1.95, "PL": 1.41, "ES": 1.55, "AT": 1.68}

udata = {}

def ud(uid):
    if uid not in udata:
        udata[uid] = {"from": "", "to": "", "weight": 40.0, "step": ""}
    return udata[uid]

async def geocode(city):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": "GidTrackBot/4.0"}
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params={"q": city, "format": "json", "limit": 1, "addressdetails": 1}, headers=headers) as r:
                data = await r.json()
                if data:
                    d = data[0]
                    cc = d.get("address", {}).get("country_code", "").upper()
                    return float(d["lon"]), float(d["lat"]), cc
    except: return None, None, None

async def get_route(lon1, lat1, lon2, lat2):
    if ORS_KEY:
        try:
            url = "https://api.openrouteservice.org/v2/directions/driving-hgv"
            headers = {"Authorization": ORS_KEY, "Content-Type": "application/json"}
            payload = {"coordinates": [[lon1, lat1], [lon2, lat2]], "units": "km"}
            async with aiohttp.ClientSession() as s:
                async with s.post(url, json=payload, headers=headers, timeout=15) as r:
                    if r.status == 200:
                        data = await r.json()
                        sumry = data["routes"][0]["summary"]
                        return round(sumry["distance"]), "🚚 Грузовой (ORS)"
        except: pass
    
    # Резервный OSRM
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                data = await r.json()
                return round(data["routes"][0]["distance"] / 1000), "🚗 Общий (OSRM)"
    except: return None, None

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚛 *GidTrack Bot*\nРассчитаю маршрут и расходы для фуры.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📏 Построить маршрут", callback_data="start_route")]]),
        parse_mode="Markdown")

async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = ud(q.from_user.id)
    
    if q.data == "start_route":
        u["step"] = "from"
        await q.edit_message_text("🏢 Введите город отправления (например: Lyon):")
    elif q.data.startswith("w_"):
        weight = float(q.data[2:])
        await q.edit_message_text("🛰 Связь со спутником... Считаю.")
        
        lon1, lat1, cc1 = await geocode(u["from"])
        lon2, lat2, cc2 = await geocode(u["to"])
        
        km, rtype = await get_route(lon1, lat1, lon2, lat2)
        if km:
            # Расчет
            cons = 18 if weight < 12 else 34
            fuel = round((km * cons / 100) * ((DIESEL.get(cc1, 1.65) + DIESEL.get(cc2, 1.65)) / 2))
            
            # Ссылка на Google Maps
            maps_url = f"https://www.google.com/maps/dir/?api=1&origin={lat1},{lon1}&destination={lat2},{lon2}&travelmode=driving"
            
            res = (f"🚩 *{u['from'].title()} — {u['to'].title()}*\n"
                   f"⚙️ Режим: {rtype}\n\n"
                   f"🛣 Дистанция: {km} км\n"
                   f"⛽ Топливо: ~{fuel}€\n\n"
                   f"[📲 ОТКРЫТЬ НАВИГАТОР]({maps_url})")
            await q.edit_message_text(res, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await q.edit_message_text("❌ Ошибка. Напишите города латиницей.")

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = ud(update.effective_user.id)
    if u["step"] == "from":
        u["from"] = update.message.text
        u["step"] = "to"
        await update.message.reply_text("🏁 Введите город назначения:")
    elif u["step"] == "to":
        u["to"] = update.message.text
        u["step"] = ""
        await update.message.reply_text("⚖️ Выберите тоннаж:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("До 12т", callback_data="w_12"), InlineKeyboardButton("40т (Фура)", callback_data="w_40")]
        ]))

def main():
    if not TOKEN: return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
