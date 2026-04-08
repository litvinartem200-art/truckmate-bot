import os, logging, aiohttp, re, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ───────────────────────────────────────────────────
TOKEN   = os.environ.get("BOT_TOKEN", "")
OCR_KEY = os.environ.get("OCR_KEY", "")
ORS_KEY = os.environ.get("ORS_API_KEY", "")   # openrouteservice.org — бесплатно 2000 запросов/день

# ─── СПРАВОЧНИКИ ────────────────────────────────────────────────────────────
DIESEL = {
    "FR":1.65,"DE":1.71,"IT":1.95,"CH":1.89,"ES":1.55,"BE":1.68,
    "NL":2.05,"AT":1.68,"PL":1.41,"CZ":1.52,"SK":1.48,"HU":1.44,
    "RO":1.38,"BG":1.32,"UA":0.95,"LU":1.48,"SI":1.55,"HR":1.42,
    "RS":1.38,"BA":1.35,"AL":1.50,"MK":1.40,"ME":1.45,"GR":1.78,
}

# Стоимость платных дорог €/100км для грузовиков (зависит от осей/веса)
TOLL = {
    "FR":25.0,"DE":19.0,"IT":18.0,"ES":15.0,"AT":26.0,
    "PL":12.0,"CZ":14.0,"HU":18.0,"BE":15.0,"SI":14.0,
    "HR":16.0,"GR":10.0,"RO":8.0,"BG":6.0,"SK":10.0,
}

# Реальный расход дизеля л/100км по весу
def get_consumption(w):
    if w <= 7.5:  return 18.0
    elif w <= 12: return 22.0
    elif w <= 20: return 28.0
    elif w <= 30: return 31.0
    else:         return 34.0

# ─── ХРАНИЛИЩЕ СОСТОЯНИЙ ────────────────────────────────────────────────────
udata = {}

def ud(uid):
    if uid not in udata:
        udata[uid] = {
            "lang": "ru", "step": "",
            "from": "", "to": "",
            "from_lon": None, "from_lat": None, "from_cc": "",
            "to_lon": None,   "to_lat": None,   "to_cc":   "",
            "weight": 20.0,
        }
    return udata[uid]

# ─── ТЕКСТЫ (RU / UK / FR / EN) ─────────────────────────────────────────────
T = {
"ru": {
    "welcome":    "Привет! Я *GidTrack* — умный помощник дальнобойщика в Европе!\n\nПрокладываю грузовые маршруты, считаю топливо, дороги и границы.\n\nВыбери язык:",
    "menu":       "Главное меню GidTrack",
    "r_route":    "Маршрут LKW + стоимость",
    "r_fuel":     "Цены на дизель",
    "r_border":   "Документы на границу",
    "r_rules":    "Правила ЕС (тахограф)",
    "r_company":  "Найти фирму/адрес",
    "r_cmr":      "Скан CMR документа",
    "r_lang":     "Язык",
    "r_pro":      "Pro подписка",
    "r_back":     "Назад",
    "ask_from":   "Откуда едешь?\n\nНапиши город отправления:\n_Примеры: Lyon, Berlin, Besancon, Warsaw_",
    "ask_to":     "Куда едешь?\n\nНапиши город назначения:",
    "ask_w":      "Полный вес грузовика:",
    "w1":"до 7.5т", "w2":"7.5—12т", "w3":"12—20т", "w4":"20—40т",
    "searching":  "Прокладываю грузовой маршрут...",
    "not_found":  "Город не найден. Проверь название и попробуй ещё раз.\n\nПример: *Lyon*, *Milano*, *Berlin*",
    "ask_co":     "Напиши название фирмы и город:\n_Пример: Lidl Lyon или Carrefour Besancon_",
    "search_co":  "Ищу компанию...",
    "ask_cmr":    "Отправь фото CMR накладной.\nЯ прочитаю адрес выгрузки и построю маршрут.",
    "ocr_proc":   "Читаю документ...",
    "ocr_nokey":  "OCR недоступен. Для активации добавь переменную OCR_KEY в Railway.",
    "ors_nokey":  "ORS недоступен. Для грузовых маршрутов добавь ORS_API_KEY в Railway.\n\nИспользую стандартный маршрут OSRM.",
    "fuel_prices": (
        "Цены на дизель по Европе\n\n"
        "Самые дешёвые:\n"
        " Украина — 0.95/л\n"
        " Болгария — 1.32/л\n"
        " Румыния — 1.38/л\n"
        " Польша — 1.41/л\n"
        " Словакия — 1.48/л\n"
        " Люксембург — 1.48/л\n\n"
        "Средние:\n"
        " Испания — 1.55/л\n"
        " Хорватия — 1.42/л\n"
        " Чехия — 1.52/л\n"
        " Франция — 1.65/л\n"
        " Австрия — 1.68/л\n"
        " Германия — 1.71/л\n\n"
        "Дорогие:\n"
        " Швейцария — 1.89/л\n"
        " Италия — 1.95/л\n"
        " Нидерланды — 2.05/л\n\n"
        "Совет: заправляйся в Польше, Словакии или Люксембурге — экономия до 80 на рейсе!"
    ),
    "rules_text": (
        "Режим труда и отдыха ЕС (Рег. 561/2006)\n\n"
        "Время вождения:\n"
        "• За день: до 9 ч (2× в нед. можно 10 ч)\n"
        "• За неделю: до 56 ч\n"
        "• За 2 недели: до 90 ч\n\n"
        "Обязательный отдых:\n"
        "• После 4.5 ч езды — 45 мин перерыв\n"
        "• Ежедневный отдых — 11 ч\n"
        "• Еженедельный — 45 ч\n\n"
        "Запреты движения по странам:\n"
        "Франция: Пт 22:00 — Сб 22:00\n"
        "Германия: Вс 00:00 — 22:00 + праздники\n"
        "Италия: Сб 14:00 — Вс 22:00\n"
        "Швейцария: Сб 15:00 — Вс 23:00\n"
        "Австрия: Вс 00:00 — 22:00\n"
        "Бельгия: Сб 22:00 — Вс 22:00"
    ),
    "b_ask":       "Выбери страну для документов:",
    "pro_text":    "GidTrack Pro — 7€/месяц\n\nБесплатно:\n• 3 маршрута в месяц\n• Цены на дизель\n• Правила ЕС\n\nPro:\n• Неограниченные маршруты\n• Скан CMR\n• Стоянки TIR по маршруту\n• Документы для всех стран\n• Уведомления о запретах\n• Поддержка 24/7\n\nОформить: @gidtrack_support",
},
"uk": {
    "welcome":    "Привіт! Я *GidTrack* — розумний помічник далекобійника!\n\nПрокладаю вантажні маршрути, рахую пальне і дороги.\n\nОбери мову:",
    "menu":       "Головне меню GidTrack",
    "r_route":    "Маршрут LKW + вартість",
    "r_fuel":     "Ціни на дизель",
    "r_border":   "Документи на кордон",
    "r_rules":    "Правила ЄС (тахограф)",
    "r_company":  "Знайти фірму/адресу",
    "r_cmr":      "Скан CMR документу",
    "r_lang":     "Мова",
    "r_pro":      "Pro підписка",
    "r_back":     "Назад",
    "ask_from":   "Звідки їдеш?\n\nНапиши місто відправлення:\n_Приклади: Lyon, Berlin, Besancon_",
    "ask_to":     "Куди їдеш?\n\nНапиши місто призначення:",
    "ask_w":      "Повна вага вантажівки:",
    "w1":"до 7.5т", "w2":"7.5—12т", "w3":"12—20т", "w4":"20—40т",
    "searching":  "Прокладаю вантажний маршрут...",
    "not_found":  "Місто не знайдено. Перевір назву і спробуй ще раз.",
    "ask_co":     "Напиши назву фірми і місто:\n_Приклад: Lidl Lyon або Carrefour Besancon_",
    "search_co":  "Шукаю компанію...",
    "ask_cmr":    "Відправ фото CMR. Я прочитаю адресу вивантаження і побудую маршрут.",
    "ocr_proc":   "Читаю документ...",
    "ocr_nokey":  "OCR недоступний. Додай OCR_KEY у Railway.",
    "ors_nokey":  "ORS недоступний. Додай ORS_API_KEY у Railway.",
    "fuel_prices": "Ціни на дизель:\n\nДешево: Польща 1.41, Словаччина 1.48\nСередні: Франція 1.65, Австрія 1.68\nДорого: Швейцарія 1.89, Iталія 1.95",
    "rules_text": "Правила ЄС: день до 9г, тиждень до 56г. Після 4.5г — 45хв перерва. Щодобовий відпочинок 11г.",
    "b_ask":       "Обери країну:",
    "pro_text":    "GidTrack Pro — 7€/місяць\n\nОформити: @gidtrack_support",
},
"fr": {
    "welcome":    "Bonjour! Je suis *GidTrack* — ton assistant chauffeur en Europe!\n\nJe calcule les itinéraires poids lourds, carburant et péages.\n\nChoisis ta langue:",
    "menu":       "Menu principal GidTrack",
    "r_route":    "Itinéraire PL + coût",
    "r_fuel":     "Prix diesel",
    "r_border":   "Documents frontière",
    "r_rules":    "Règles UE (tachygraphe)",
    "r_company":  "Trouver une entreprise",
    "r_cmr":      "Scanner CMR",
    "r_lang":     "Langue",
    "r_pro":      "Abonnement Pro",
    "r_back":     "Retour",
    "ask_from":   "Ville de départ?\n\nEcris la ville:\n_Exemples: Lyon, Berlin, Besancon_",
    "ask_to":     "Ville d'arrivée?\n\nEcris la destination:",
    "ask_w":      "Poids total du camion:",
    "w1":"7.5t", "w2":"7.5—12t", "w3":"12—20t", "w4":"20—40t",
    "searching":  "Calcul itinéraire poids lourd...",
    "not_found":  "Ville non trouvée. Vérifie le nom et réessaie.",
    "ask_co":     "Nom de l'entreprise et ville:\n_Exemple: Lidl Lyon ou Carrefour Besancon_",
    "search_co":  "Recherche en cours...",
    "ask_cmr":    "Envoie une photo de la CMR. Je lirai l'adresse de livraison.",
    "ocr_proc":   "Lecture du document...",
    "ocr_nokey":  "OCR indisponible. Ajoute OCR_KEY dans Railway.",
    "ors_nokey":  "ORS indisponible. Ajoute ORS_API_KEY dans Railway.",
    "fuel_prices": "Prix diesel en Europe:\n\nPas cher: Pologne 1.41, Slovaquie 1.48\nMoyens: France 1.65, Autriche 1.68\nCher: Suisse 1.89, Italie 1.95",
    "rules_text": "Règles UE: jour max 9h, semaine max 56h. Pause après 4.5h - 45min.",
    "b_ask":       "Choisis le pays:",
    "pro_text":    "GidTrack Pro — 7€/mois\n\nAbonnement: @gidtrack_support",
},
"en": {
    "welcome":    "Hi! I'm *GidTrack* — your smart truck driver assistant in Europe!\n\nI calculate HGV routes, fuel costs and tolls.\n\nChoose language:",
    "menu":       "GidTrack Main Menu",
    "r_route":    "HGV Route + cost",
    "r_fuel":     "Diesel prices",
    "r_border":   "Border documents",
    "r_rules":    "EU rules (tachograph)",
    "r_company":  "Find company/address",
    "r_cmr":      "Scan CMR document",
    "r_lang":     "Language",
    "r_pro":      "Pro subscription",
    "r_back":     "Back",
    "ask_from":   "Where are you departing from?\n\nType the city:\n_Examples: Lyon, Berlin, Besancon_",
    "ask_to":     "Where are you going?\n\nType destination city:",
    "ask_w":      "Total truck weight:",
    "w1":"7.5t", "w2":"7.5—12t", "w3":"12—20t", "w4":"20—40t",
    "searching":  "Calculating HGV route...",
    "not_found":  "City not found. Check the name and try again.",
    "ask_co":     "Company name and city:\n_Example: Lidl Lyon or Carrefour Besancon_",
    "search_co":  "Searching...",
    "ask_cmr":    "Send a CMR photo. I'll read the delivery address.",
    "ocr_proc":   "Reading document...",
    "ocr_nokey":  "OCR unavailable. Add OCR_KEY to Railway.",
    "ors_nokey":  "ORS unavailable. Add ORS_API_KEY to Railway.",
    "fuel_prices": "Diesel prices in Europe:\n\nCheap: Poland 1.41, Slovakia 1.48\nAverage: France 1.65, Austria 1.68\nExpensive: Switzerland 1.89, Italy 1.95",
    "rules_text": "EU rules: day max 9h, week max 56h. Break after 4.5h - 45min.",
    "b_ask":       "Choose country:",
    "pro_text":    "GidTrack Pro — 7€/month\n\nSubscribe: @gidtrack_support",
},
}

# ─── ДОКУМЕНТЫ ДЛЯ ГРАНИЦ ───────────────────────────────────────────────────
BORDER = {
"CH": {
    "ru": ("ШВЕЙЦАРИЯ — ДОКУМЕНТЫ\n\n"
           "Обязательно:\n"
           " CMR накладная\n"
           " Права CE + карточка водителя\n"
           " Техпаспорт\n"
           " Страховка (Зелёная карта)\n"
           " Виньетка 40 CHF обязательно!\n"
           " Разрешение ЕКМТ\n\n"
           "Для груза:\n"
           " Декларация T1/T2\n"
           " Санит. сертификаты (если продукты)\n\n"
           "ВАЖНО: Швейцария не в ЕС — нужна таможня!\n"
           "Запрет ночью: 22:00—05:00\n"
           "Запрет по воскресеньям"),
    "uk": "ШВЕЙЦАРІЯ:\n CMR\n Права CE\n Зелена картка\n Víньєтка 40 CHF!\n ЄКМТ\n\nМитниця обов'язкова! Заборона ніч 22:00-05:00 та неділя",
    "fr": "SUISSE:\n CMR\n Permis CE + carte\n Carte Verte\n Vignette 40 CHF!\n CEMT\n\nDouane obligatoire! Interdiction nuit 22h-05h et dimanche",
    "en": "SWITZERLAND:\n CMR note\n CE license + card\n Green Card\n Vignette 40 CHF!\n ECMT permit\n\nCustoms required! Night ban 22:00-05:00 and Sunday",
},
"DE": {
    "ru": ("ГЕРМАНИЯ — ДОКУМЕНТЫ\n\n"
           "Обязательно:\n"
           " CMR накладная\n"
           " Права CE + карточка водителя\n"
           " Техпаспорт + Зелёная карта\n"
           " Maut (toll-collect.de) — обязателен!\n\n"
           "Важно:\n"
           " Maut для грузовиков 7.5т+\n"
           " Запрет по воскресеньям и праздникам\n"
           " Минимум Euro 4 в городских зонах\n"
           " Тахограф обязателен"),
    "uk": "НIМЕЧЧИНА:\n CMR\n Права CE\n Зелена картка\n Maut toll-collect.de!\n\nЗаборона в неділю та свята. Euro 4 у містах.",
    "fr": "ALLEMAGNE:\n CMR\n Permis CE\n Carte Verte\n Maut toll-collect.de!\n\nInterdiction dimanche et fériés. Euro 4 en ville.",
    "en": "GERMANY:\n CMR note\n CE license\n Green Card\n Maut toll-collect.de!\n\nSunday and holiday ban. Euro 4 in cities.",
},
"IT": {
    "ru": ("ИТАЛИЯ — ДОКУМЕНТЫ\n\n"
           "Обязательно:\n"
           " CMR накладная\n"
           " Права CE + карточка водителя\n"
           " Техпаспорт + Зелёная карта\n"
           " Autostrada — платные дороги\n\n"
           "Запреты движения:\n"
           " Суббота 14:00 — 22:00\n"
           " Воскресенье 07:00 — 22:00\n"
           " Канун праздников\n\n"
           "Осторожно: зоны ZTL в городах — штрафы!"),
    "uk": "IТАЛІЯ:\n CMR\n Права CE\n Зелена картка\n Autostrada платна\n\nЗаборона: Сб 14-22, Нд 07-22. Зони ZTL штрафи!",
    "fr": "ITALIE:\n CMR\n Permis CE\n Carte Verte\n Autostrade payantes\n\nInterdiction: Sam 14h-22h, Dim 07h-22h. Zones ZTL amendes!",
    "en": "ITALY:\n CMR note\n CE license\n Green Card\n Autostrade tolls\n\nBan: Sat 14:00-22:00, Sun 07:00-22:00. ZTL zones - fines!",
},
"FR": {
    "ru": ("ФРАНЦИЯ — ДОКУМЕНТЫ\n\n"
           "Обязательно:\n"
           " CMR накладная\n"
           " Права CE + карточка водителя\n"
           " Техпаспорт + Зелёная карта\n"
           " Péage — платные дороги (карта/наличные)\n"
           " Crit'Air виньетка (в городских зонах)\n\n"
           "Запрет: Пятница 22:00 — Суббота 22:00\n"
           "Некоторые праздники — весь день"),
    "uk": "ФРАНЦІЯ:\n CMR\n Права CE\n Зелена картка\n Crit'Air обов'язковий у містах\n\nЗаборона: Пт 22:00 - Сб 22:00",
    "fr": "FRANCE:\n CMR\n Permis CE\n Carte Verte\n Péage\n Vignette Crit'Air en ville\n\nInterdiction: Ven 22h - Sam 22h",
    "en": "FRANCE:\n CMR note\n CE license\n Green Card\n Péage tolls\n Crit'Air vignette in cities\n\nBan: Fri 22:00 - Sat 22:00",
},
"AT": {
    "ru": ("АВСТРИЯ — ДОКУМЕНТЫ\n\n"
           "Обязательно:\n"
           " CMR накладная\n"
           " Права CE + карточка водителя\n"
           " Техпаспорт + Зелёная карта\n"
           " Maut (go-maut.at) — обязателен для 3.5т+\n"
           " ЕКМТ или двустороннее разрешение\n\n"
           "Запрет: Воскресенье 00:00 — 22:00\n"
           "Ночной запрет на горных дорогах"),
    "uk": "АВСТРІЯ:\n CMR\n Права CE\n Зелена картка\n Maut go-maut.at!\n\nЗаборона нд 00:00-22:00",
    "fr": "AUTRICHE:\n CMR\n Permis CE\n Carte Verte\n Maut go-maut.at!\n\nInterdiction dimanche 00h-22h",
    "en": "AUSTRIA:\n CMR note\n CE license\n Green Card\n Maut go-maut.at!\n\nSunday ban 00:00-22:00",
},
}

# ─── API: ГЕОКОДИНГ ──────────────────────────────────────────────────────────
async def geocode(city: str):
    """Nominatim — бесплатно, без ключа"""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": city, "format": "json",
            "limit": 1, "addressdetails": 1,
        }
        headers = {"User-Agent": "GidTrackBot/4.0 contact@gidtrack.eu"}
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params=params, headers=headers,
                             timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
                if data:
                    d  = data[0]
                    cc = d.get("address", {}).get("country_code", "").upper()
                    return float(d["lon"]), float(d["lat"]), d["display_name"], cc
    except Exception as e:
        logger.error(f"geocode error: {e}")
    return None, None, None, None

# ─── API: МАРШРУТ ────────────────────────────────────────────────────────────
async def get_route_ors(lon1, lat1, lon2, lat2, weight_t):
    """OpenRouteService — грузовой маршрут с ограничениями по весу и высоте"""
    if not ORS_KEY:
        return None, None
    try:
        url = "https://api.openrouteservice.org/v2/directions/driving-hgv"
        payload = {
            "coordinates": [[lon1, lat1], [lon2, lat2]],
            "units": "km",
            "vehicle_type": "hgv",
            "options": {
                "vehicle_type": "hgv",
                "profile_params": {
                    "weightings": {
                        "steepness_difficulty": {"level": 1}
                    },
                    "restrictions": {
                        "weight": weight_t,
                        "axleload": round(weight_t / 4, 1),
                        "height": 4.0,
                        "width": 2.55,
                        "length": 16.5
                    }
                }
            }
        }
        headers = {
            "Authorization": ORS_KEY,
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, headers=headers,
                              timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status == 200:
                    data = await r.json()
                    seg = data["routes"][0]["summary"]
                    km  = round(seg["distance"])
                    mins = round(seg["duration"] / 60)
                    h, m = divmod(mins, 60)
                    dur = f"{h}ч{m:02d}м" if m else f"{h}ч"
                    return km, dur
                else:
                    body = await r.text()
                    logger.error(f"ORS error {r.status}: {body[:200]}")
    except Exception as e:
        logger.error(f"ORS route error: {e}")
    return None, None

async def get_route_osrm(lon1, lat1, lon2, lat2):
    """OSRM — резервный бесплатный маршрут без ключа"""
    try:
        url = (f"http://router.project-osrm.org/route/v1/driving/"
               f"{lon1},{lat1};{lon2},{lat2}")
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params={"overview": "false"},
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                data = await r.json()
                if data.get("code") == "Ok":
                    rt = data["routes"][0]
                    km   = round(rt["distance"] / 1000)
                    mins = round(rt["duration"] / 60)
                    h, m = divmod(mins, 60)
                    dur  = f"{h}ч{m:02d}м" if m else f"{h}ч"
                    return km, dur
    except Exception as e:
        logger.error(f"OSRM error: {e}")
    return None, None

async def smart_route(lon1, lat1, lon2, lat2, weight_t):
    """Сначала ORS (грузовой), если нет ключа — OSRM"""
    if ORS_KEY:
        km, dur = await get_route_ors(lon1, lat1, lon2, lat2, weight_t)
        if km:
            return km, dur, "ORS-HGV"
    km, dur = await get_route_osrm(lon1, lat1, lon2, lat2)
    if km:
        return km, dur, "OSRM"
    return None, None, None

# ─── API: ПОИСК КОМПАНИЙ ─────────────────────────────────────────────────────
async def find_company(query: str):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "limit": 3, "addressdetails": 1}
        headers = {"User-Agent": "GidTrackBot/4.0 contact@gidtrack.eu"}
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params=params, headers=headers,
                             timeout=aiohttp.ClientTimeout(total=10)) as r:
                return await r.json()
    except Exception as e:
        logger.error(f"company search error: {e}")
    return []

# ─── API: OCR ────────────────────────────────────────────────────────────────
async def do_ocr(photo_bytes: bytes):
    if not OCR_KEY:
        return None
    try:
        import base64
        b64 = base64.b64encode(photo_bytes).decode()
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://api.ocr.space/parse/image",
                data={
                    "base64Image": f"data:image/jpeg;base64,{b64}",
                    "apikey": OCR_KEY,
                    "language": "eng",
                    "isOverlayRequired": False,
                    "detectOrientation": True,
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as r:
                res = await r.json()
                if res.get("IsErroredOnProcessing"):
                    return None
                pr = res.get("ParsedResults", [])
                if pr:
                    return pr[0].get("ParsedText", "")
    except Exception as e:
        logger.error(f"OCR error: {e}")
    return None

def extract_address(text: str):
    """Вытащить адрес из OCR-текста CMR"""
    keywords = [
        "street","rue","str.","strasse","via","viale","allee","avenue",
        "blvd","boulevard","road","rd","lane","place","piazza","platz",
        "ul.","ул.","вул.","alej","gasse",
    ]
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines:
        ll = line.lower()
        if any(k in ll for k in keywords) and 8 < len(line) < 120:
            return line
    for line in lines:
        if re.search(r'\b\d{4,5}\b', line) and 8 < len(line) < 120:
            return line
    return None

# ─── РАСЧЁТ СТОИМОСТИ ────────────────────────────────────────────────────────
def build_cost(km, cc1, cc2, weight, lang, route_type="OSRM"):
    cons  = get_consumption(weight)
    fp1   = DIESEL.get(cc1, 1.65)
    fp2   = DIESEL.get(cc2, 1.65)
    fp    = round((fp1 + fp2) / 2, 2)
    fl    = round(km * cons / 100)
    fc    = round(fl * fp)
    ch_fee = CH_VIGNETTE = 42
    if cc1 == "CH" or cc2 == "CH":
        toll = ch_fee
        toll_label = "Виньетка CH" if lang=="ru" else "Víньєтка CH" if lang=="uk" else "Vignette CH"
    else:
        rate  = max(TOLL.get(cc1, 10), TOLL.get(cc2, 10))
        toll  = round(km * rate / 100)
        toll_label = "Платные дороги" if lang=="ru" else "Платні дороги" if lang=="uk" else "Péages" if lang=="fr" else "Tolls"
    total = fc + toll
    cheapest_cc = min(DIESEL, key=DIESEL.get)
    saving = round(fl * (fp - DIESEL[cheapest_cc]))
    country_names = {
        "BG":"Болгария","UA":"Украина","RO":"Румыния","PL":"Польша",
        "SK":"Словакия","LU":"Люксембург","HU":"Венгрия","HR":"Хорватия",
    }
    if lang == "ru":
        lines = [
            f"Расстояние: {km} км | Время: {{dur}}",
            f"Вес: {weight}т | Расход: {cons}л/100км",
            "",
            f"Топливо: {fl}л x {fp}/л = {fc}",
            f"{toll_label}: {toll}",
            "",
            f"ИТОГО: {total}",
        ]
        if saving > 10:
            cheap_name = country_names.get(cheapest_cc, cheapest_cc)
            lines.append(f"\nСовет: заправись в {cheap_name} — экономия ~{saving}")
        if route_type == "OSRM":
            lines.append("\n(Маршрут общий. Для грузового ORS добавь ORS_API_KEY)")
    elif lang == "uk":
        lines = [
            f"Відстань: {km} км | Час: {{dur}}",
            f"Вага: {weight}т | Витрата: {cons}л/100км",
            "",
            f"Пальне: {fl}л x {fp}/л = {fc}",
            f"{toll_label}: {toll}",
            "",
            f"РАЗОМ: {total}",
        ]
    elif lang == "fr":
        lines = [
            f"Distance: {km} km | Durée: {{dur}}",
            f"Poids: {weight}t | Conso: {cons}l/100km",
            "",
            f"Carburant: {fl}l x {fp}/l = {fc}",
            f"{toll_label}: {toll}",
            "",
            f"TOTAL: {total}",
        ]
    else:
        lines = [
            f"Distance: {km} km | Time: {{dur}}",
            f"Weight: {weight}t | Consumption: {cons}l/100km",
            "",
            f"Fuel: {fl}l x {fp}/l = {fc}",
            f"{toll_label}: {toll}",
            "",
            f"TOTAL: {total}",
        ]
    return "\n".join(lines), total

# ─── КЛАВИАТУРЫ ─────────────────────────────────────────────────────────────
def kb_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Украинский", callback_data="lang_uk"),
         InlineKeyboardButton("Русский",    callback_data="lang_ru")],
        [InlineKeyboardButton("Francais",   callback_data="lang_fr"),
         InlineKeyboardButton("English",    callback_data="lang_en")],
    ])

def kb_menu(uid):
    l = ud(uid)["lang"]
    t = T[l]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["r_route"],   callback_data="m_route")],
        [InlineKeyboardButton(t["r_fuel"],    callback_data="m_fuel"),
         InlineKeyboardButton(t["r_rules"],   callback_data="m_rules")],
        [InlineKeyboardButton(t["r_border"],  callback_data="m_border")],
        [InlineKeyboardButton(t["r_company"], callback_data="m_company"),
         InlineKeyboardButton(t["r_cmr"],     callback_data="m_cmr")],
        [InlineKeyboardButton(t["r_pro"],     callback_data="m_pro"),
         InlineKeyboardButton(t["r_lang"],    callback_data="m_lang")],
    ])

def kb_back(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(T[ud(uid)["lang"]]["r_back"], callback_data="back")]
    ])

def kb_weight(uid):
    l = ud(uid)["lang"]
    t = T[l]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["w1"], callback_data="w_7.5"),
         InlineKeyboardButton(t["w2"], callback_data="w_12")],
        [InlineKeyboardButton(t["w3"], callback_data="w_20"),
         InlineKeyboardButton(t["w4"], callback_data="w_40")],
        [InlineKeyboardButton(t["r_back"], callback_data="back")],
    ])

def kb_border(uid):
    l = ud(uid)["lang"]
    t = T[l]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Швейцария / Suisse",   callback_data="b_CH")],
        [InlineKeyboardButton("Германия / Allemagne", callback_data="b_DE")],
        [InlineKeyboardButton("Италия / Italie",      callback_data="b_IT")],
        [InlineKeyboardButton("Франция / France",     callback_data="b_FR")],
        [InlineKeyboardButton("Австрия / Autriche",   callback_data="b_AT")],
        [InlineKeyboardButton(t["r_back"],             callback_data="back")],
    ])

def kb_after_route(uid):
    l = ud(uid)["lang"]
    t = T[l]
    lbl = "Новый маршрут" if l=="ru" else "Новий маршрут" if l=="uk" else "Nouvel itinéraire" if l=="fr" else "New route"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbl, callback_data="m_route")],
        [InlineKeyboardButton(t["r_border"], callback_data="m_border"),
         InlineKeyboardButton(t["r_fuel"],   callback_data="m_fuel")],
        [InlineKeyboardButton(t["r_back"],   callback_data="back")],
    ])

# ─── ХЭНДЛЕРЫ ───────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud(uid)["step"] = ""
    await update.message.reply_text(
        T["ru"]["welcome"],
        reply_markup=kb_lang(),
        parse_mode="Markdown"
    )

async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u   = ud(uid)
    l   = u["lang"]
    t   = T[l]
    d   = q.data

    # ЯЗЫК
    if d.startswith("lang_"):
        u["lang"] = d[5:]
        l = u["lang"]
        t = T[l]
        u["step"] = ""
        await q.edit_message_text(
            t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")

    elif d in ("back", "m_lang"):
        u["step"] = ""
        if d == "m_lang":
            await q.edit_message_text(
                t["welcome"], reply_markup=kb_lang(), parse_mode="Markdown")
        else:
            await q.edit_message_text(
                t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")

    elif d == "m_fuel":
        await q.edit_message_text(
            t["fuel_prices"], reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d == "m_rules":
        await q.edit_message_text(
            t["rules_text"], reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d == "m_pro":
        await q.edit_message_text(
            t["pro_text"], reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d == "m_border":
        await q.edit_message_text(
            t["b_ask"], reply_markup=kb_border(uid), parse_mode="Markdown")

    elif d.startswith("b_"):
        cc  = d[2:]
        doc = BORDER.get(cc, {}).get(l) or BORDER.get(cc, {}).get("ru", "Не найдено")
        await q.edit_message_text(
            doc, reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d == "m_route":
        u["step"] = "from"
        await q.edit_message_text(
            t["ask_from"], reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d == "m_company":
        u["step"] = "company"
        await q.edit_message_text(
            t["ask_co"], reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d == "m_cmr":
        if not OCR_KEY:
            await q.edit_message_text(
                t["ocr_nokey"], reply_markup=kb_back(uid), parse_mode="Markdown")
        else:
            u["step"] = "cmr"
            await q.edit_message_text(
                t["ask_cmr"], reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d.startswith("w_"):
        weight = float(d[2:])
        u["weight"] = weight
        await q.edit_message_text(t["searching"], parse_mode="Markdown")

        lon1, lat1, name1, cc1 = await geocode(u.get("from", ""))
        lon2, lat2, name2, cc2 = await geocode(u.get("to", ""))

        if not (lon1 and lon2):
            await q.edit_message_text(
                t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return

        km, dur, rtype = await smart_route(lon1, lat1, lon2, lat2, weight)
        if not km:
            await q.edit_message_text(
                t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return

        cost_text, total = build_cost(km, cc1 or "FR", cc2 or "FR", weight, l, rtype)
        cost_text = cost_text.replace("{dur}", str(dur))

        city_f = u.get("from", "").title()
        city_t = u.get("to", "").title()
        route_lbl = "Грузовой маршрут ORS" if rtype=="ORS-HGV" else "Стандартный маршрут"

        header = f"{city_f} — {city_t}\n{route_lbl}\n\n"
        await q.edit_message_text(
            header + cost_text,
            reply_markup=kb_after_route(uid),
            parse_mode="Markdown"
        )

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text.strip()
    u    = ud(uid)
    l    = u["lang"]
    t    = T[l]
    step = u.get("step", "")

    if step == "from":
        u["from"] = text
        u["step"] = "to"
        await update.message.reply_text(
            t["ask_to"], reply_markup=kb_back(uid), parse_mode="Markdown")

    elif step == "to":
        u["to"] = text
        u["step"] = "weight"
        await update.message.reply_text(
            t["ask_w"], reply_markup=kb_weight(uid), parse_mode="Markdown")

    elif step == "company":
        await update.message.reply_text(t["search_co"], parse_mode="Markdown")
        results = await find_company(text)
        if not results:
            await update.message.reply_text(
                t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        lines = []
        for i, r in enumerate(results[:3], 1):
            name = r.get("display_name", "")[:90]
            lat, lon = r.get("lat"), r.get("lon")
            maps_url = f"https://maps.google.com/?q={lat},{lon}"
            lines.append(f"{i}. {name}\n{maps_url}")
        await update.message.reply_text(
            "\n\n".join(lines),
            reply_markup=kb_back(uid),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    else:
        u["step"] = ""
        await update.message.reply_text(
            t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")

async def photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u   = ud(uid)
    l   = u["lang"]
    t   = T[l]

    if u.get("step") != "cmr":
        await update.message.reply_text(
            t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")
        return

    await update.message.reply_text(t["ocr_proc"], parse_mode="Markdown")
    photo     = update.message.photo[-1]
    file_obj  = await ctx.bot.get_file(photo.file_id)
    bio       = await file_obj.download_as_bytearray()
    ocr_text  = await do_ocr(bytes(bio))

    if not ocr_text:
        await update.message.reply_text(
            t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
        return

    address = extract_address(ocr_text)
    if address:
        u["to"]   = address
        u["step"] = "weight"
        found_lbl  = "Адрес найден" if l=="ru" else "Адресу знайдено" if l=="uk" else "Adresse trouvée" if l=="fr" else "Address found"
        weight_lbl = "Укажи вес грузовика:" if l=="ru" else "Вкажи вагу:" if l=="uk" else "Indique le poids:" if l=="fr" else "Select weight:"
        await update.message.reply_text(
            f"{found_lbl}:\n{address}\n\n{weight_lbl}",
            reply_markup=kb_weight(uid),
            parse_mode="Markdown"
        )
    else:
        preview = ocr_text[:500]
        await update.message.reply_text(
            f"Текст из CMR:\n{preview}\n\nАдрес не определён автоматически. Введи вручную.",
            reply_markup=kb_back(uid),
            parse_mode="Markdown"
        )

# ─── ЗАПУСК ──────────────────────────────────────────────────────────────────
def main():
    if not TOKEN:
        logger.error("BOT_TOKEN не задан!")
        return
    if not ORS_KEY:
        logger.warning("ORS_API_KEY не задан — будет использован стандартный OSRM")
    if not OCR_KEY:
        logger.warning("OCR_KEY не задан — скан CMR недоступен")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("GidTrack Bot v4 запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
