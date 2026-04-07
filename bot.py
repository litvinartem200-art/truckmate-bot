import os, logging, aiohttp, re, openrouteservice
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN   = os.environ.get("BOT_TOKEN", "")
OCR_KEY = os.environ.get("OCR_KEY", "")
ORS_KEY = os.environ.get("ORS_API_KEY", "")

ors_client = None
if ORS_KEY:
    ors_client = openrouteservice.Client(key=ORS_KEY)

DIESEL = {
    "FR":1.65,"DE":1.71,"IT":1.95,"CH":1.89,"ES":1.55,"BE":1.68,
    "NL":2.05,"AT":1.68,"PL":1.41,"CZ":1.52,"SK":1.48,"HU":1.44,
    "RO":1.38,"BG":1.32,"UA":0.95,"LU":1.48,"SI":1.55,"HR":1.42,
}

TOLL_PER_100 = {
    "FR":25.0,"DE":19.0,"IT":18.0,"ES":15.0,"AT":26.0,"PL":12.0,
    "CZ":14.0,"HU":18.0,"BE":15.0,"SI":14.0,"HR":16.0,
}

udata = {}
def ud(uid):
    if uid not in udata: udata[uid] = {"lang":"ru","step":""}
    return udata[uid]

def consumption(w):
    if w<=7.5: return 18.0
    elif w<=12: return 22.0
    elif w<=20: return 28.0
    return 33.0

T = {
"ru":{
  "welcome":"Привет! Я *GidTrack* — помощник дальнобойщика! Выбери язык:",
  "menu":"Главное меню GidTrack",
  "r_route":"Маршрут LKW","r_fuel":"Цены дизель","r_border":"Границы","r_rules":"Правила ЕС",
  "r_company":"Фирма/Адрес","r_cmr":"Скан CMR","r_lang":"Язык","r_pro":"Pro","r_back":"Назад",
  "ask_from":"Откуда? (Город):","ask_to":"Куда? (Город):","ask_w":"Вес фуры:",
  "w1":"до 7.5т","w2":"12т","w3":"20т","w4":"40т",
  "searching":"Рассчитываю маршрут LKW...","not_found":"Не найдено. Проверь название города.",
  "ask_co":"Название фирмы и город:","ask_cmr":"Отправь фото CMR:","fuel":"Цены на сегодня:",
  "rules":"Режим труда и отдыха ЕС...", "b_ask":"Выбери страну:", "pro":"GidTrack Pro @gidtrack_support"
},
"uk":{
  "welcome":"Привіт! Я *GidTrack*! Обери мову:", "menu":"Головне меню",
  "r_route":"Маршрут LKW","r_fuel":"Ціни дизель","r_border":"Кордони","r_rules":"Правила ЄС",
  "r_company":"Фірма/Адреса","r_cmr":"Скан CMR","r_lang":"Мова","r_pro":"Pro","r_back":"Назад",
  "ask_from":"Звідки?","ask_to":"Куди?","ask_w":"Вага фури:",
  "w1":"до 7.5т","w2":"12т","w3":"20т","w4":"40т",
  "searching":"Рахую маршрут LKW...","not_found":"Не знайдено.",
  "ask_co":"Назва фірми:","ask_cmr":"Фото CMR:","fuel":"Ціни сьогодні:",
  "rules":"Правила ЄС...","b_ask":"Обери країну:","pro":"GidTrack Pro @gidtrack_support"
},
"fr":{
  "welcome":"Bonjour! Choisi ta langue:","menu":"Menu GidTrack",
  "r_route":"Itinéraire LKW","r_fuel":"Prix diesel","r_border":"Frontières","r_rules":"Règles UE",
  "r_company":"Entreprise","r_cmr":"Scan CMR","r_lang":"Langue","r_pro":"Abonnement Pro","r_back":"Retour",
  "ask_from":"Départ?","ask_to":"Arrivée?","ask_w":"Poids camion:",
  "w1":"7.5t","w2":"12t","w3":"20t","w4":"40t",
  "searching":"Calcul itinéraire camion...","not_found":"Non trouvé.",
  "ask_co":"Nom entreprise:","ask_cmr":"Photo CMR:","fuel":"Prix diesel:",
  "rules":"Règles UE...","b_ask":"Pays:","pro":"GidTrack Pro @gidtrack_support"
}
}

async def geocode(city):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": city, "format": "json", "limit": 1, "addressdetails": 1}
        headers = {"User-Agent": "GidTrackBot/3.0"}
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params=params, headers=headers) as r:
                data = await r.json()
                if data:
                    d = data[0]
                    cc = d.get("address", {}).get("country_code", "").upper()
                    return float(d["lon"]), float(d["lat"]), cc
    except: return None, None, None

async def get_truck_route(lon1, lat1, lon2, lat2):
    if not ors_client: return None, None
    try:
        coords = ((lon1, lat1), (lon2, lat2))
        routes = ors_client.directions(coordinates=coords, profile='driving-hgv', format='geojson', units='km')
        rt = routes['features'][0]['properties']['summary']
        km = round(rt['distance'])
        h, m = divmod(round(rt['duration'] / 60), 60)
        return km, f"{h}h{m:02d}"
    except: return None, None

def build_cost(km, cc1, cc2, weight, lang):
    cons = consumption(weight)
    p1 = DIESEL.get(cc1, 1.65)
    p2 = DIESEL.get(cc2, 1.65)
    price = round((p1 + p2) / 2, 2)
    fuel_total = round((km * cons / 100) * price)
    tolls = round(km * max(TOLL_PER_100.get(cc1, 15), TOLL_PER_100.get(cc2, 15)) / 100)
    total = fuel_total + tolls
    if cc1 == "CH" or cc2 == "CH": total += 42
    if lang == "ru": return f"Топливо: ~{fuel_total}€\nДороги: ~{tolls}€\n*ИТОГО: {total}€*"
    if lang == "fr": return f"Carburant: ~{fuel_total}€\nPéages: ~{tolls}€\n*TOTAL: {total}€*"
    return f"Fuel: ~{fuel_total}€\nTolls: ~{tolls}€\n*TOTAL: {total}€*"

def kb_lang():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Українська", callback_data="l_uk"), InlineKeyboardButton("Русский", callback_data="l_ru")],[InlineKeyboardButton("Français", callback_data="l_fr")]])

def kb_menu(uid):
    l=ud(uid)["lang"]; t=T.get(l, T["ru"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["r_route"], callback_data="m_route")],
        [InlineKeyboardButton(t["r_fuel"], callback_data="m_fuel"), InlineKeyboardButton(t["r_rules"], callback_data="m_rules")],
        [InlineKeyboardButton(t["r_company"], callback_data="m_company"), InlineKeyboardButton(t["r_cmr"], callback_data="m_cmr")],
        [InlineKeyboardButton(t["r_lang"], callback_data="m_lang")]
    ])

def kb_back(uid):
    l=ud(uid)["lang"]; t=T.get(l, T["ru"])
    return InlineKeyboardMarkup([[InlineKeyboardButton(t["r_back"], callback_data="back")]])

def kb_w(uid):
    l=ud(uid)["lang"]; t=T.get(l, T["ru"])
    return InlineKeyboardMarkup([[InlineKeyboardButton(t["w1"], callback_data="w_7.5"), InlineKeyboardButton(t["w2"], callback_data="w_12")],[InlineKeyboardButton(t["w3"], callback_data="w_20"), InlineKeyboardButton(t["w4"], callback_data="w_40")]])

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выберите язык / Choisissez la langue:", reply_markup=kb_lang())

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; u = ud(uid); d = q.data
    if d.startswith("l_"):
        u["lang"] = d[2:]; await q.edit_message_text(T[u["lang"]]["menu"], reply_markup=kb_menu(uid))
    elif d == "m_lang": await q.edit_message_text("Язык / Langue:", reply_markup=kb_lang())
    elif d == "back": await q.edit_message_text(T[u["
