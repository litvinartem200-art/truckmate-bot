import os
import logging
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
ORS_KEY = os.environ.get("ORS_KEY", "")

# Fuel prices per country (updated manually or via API)
FUEL_PRICES = {
    "FR": 1.65, "CH": 1.89, "DE": 1.71, "IT": 1.95,
    "ES": 1.55, "BE": 1.68, "NL": 2.05, "AT": 1.68,
    "PL": 1.41, "CZ": 1.52, "SK": 1.48, "HU": 1.44,
    "RO": 1.38, "BG": 1.32, "UA": 0.95,
}

# Toll costs per country for trucks (€ per 100km approx)
TOLL_PER_100KM = {
    "FR": 6.0, "IT": 7.5, "ES": 5.0, "AT": 4.5,
    "DE": 2.5, "BE": 1.5, "PL": 2.0, "CZ": 2.0,
    "CH": 0, "NL": 0, "HU": 3.0,
}

# Switzerland vignette
CH_VIGNETTE = 42

TEXTS = {
    "uk": {
        "welcome": "👋 Вітаю в *GidTrack Bot*!\n\nТвій помічник далекобійника в Європі 🚛\n\nОбери мову / Choose language:",
        "menu_title": "🚛 *Головне меню*",
        "route": "🗺️ Прокласти маршрут",
        "fuel": "⛽ Ціни на пальне",
        "border": "🛂 Документи на кордон",
        "rules": "📋 Правила ЄС",
        "back": "◀️ Назад",
        "language": "🌍 Мова",
        "route_ask_from": "📍 *Звідки їдеш?*\n\nНапиши місто відправлення:\n\nПриклади: _Lyon_, _Paris_, _Besançon_, _Milano_",
        "route_ask_to": "📍 *Куди їдеш?*\n\nНапиши місто призначення:",
        "route_ask_weight": "⚖️ *Повна вага вантажівки:*",
        "w1": "до 7.5т",
        "w2": "7.5 — 12т",
        "w3": "12 — 40т",
        "searching": "🔍 Шукаю маршрут...",
        "not_found": "❌ Місто не знайдено. Перевір назву і спробуй ще раз.\n\nПриклад: *Lyon*, *Munich*, *Roma*",
        "fuel_title": "⛽ *Ціни на дизель сьогодні*\n\n🟢 Найдешевші:\n🇧🇬 Болгарія — 1.32€/л\n🇵🇱 Польща — 1.41€/л\n🇸🇰 Словаччина — 1.48€/л\n\n🟡 Середні:\n🇫🇷 Франція — 1.65€/л\n🇩🇪 Німеччина — 1.71€/л\n🇦🇹 Австрія — 1.68€/л\n\n🔴 Найдорожчі:\n🇨🇭 Швейцарія — 1.89€/л\n🇮🇹 Італія — 1.95€/л\n🇳🇱 Нідерланди — 2.05€/л\n\n_Оновлено сьогодні_",
        "rules_text": "📋 *Правила водія ЄС (рег. 561/2006)*\n\n⏱️ *Час водіння:*\n• День: макс. *9 год* (2×/тиж до 10г)\n• Тиждень: макс. *56 год*\n• 2 тижні: макс. *90 год*\n\n😴 *Обов'язковий відпочинок:*\n• Після 4.5г — *45 хвилин*\n• Щодобовий — *11 год*\n• Щотижневий — *45 год*\n\n🚫 *Заборони руху:*\n🇫🇷 Пт 22:00 — Сб 22:00\n🇩🇪 Неділя + свята\n🇮🇹 Сб 14:00 — Нд 22:00\n🇨🇭 Сб 15:00 — Нд 23:00",
        "border_ch": "🇨🇭 *Швейцарія — документи*\n\n✅ CMR накладна\n✅ Права CE + картка водія\n✅ Техпаспорт\n✅ Зелена картка\n✅ Віньєтка 40 CHF ⚠️\n✅ Дозвіл ЄКМТ\n\n📦 *Для вантажу:*\n• Декларація T1/T2\n• Санітарні сертифікати\n\n⚠️ Швейцарія — не ЄС!\n🌙 Заборона 22:00-05:00\n🚫 Заборона в неділю",
        "border_de": "🇩🇪 *Німеччина — документи*\n\n✅ CMR накладна\n✅ Права CE + картка водія\n✅ Техпаспорт\n✅ Зелена картка\n✅ Maut (toll-collect.de)\n\n⚠️ Maut обов'язковий для 7.5т+\n🚫 Заборона в неділю\n🏙️ Мінімум Euro 4 у містах",
        "border_it": "🇮🇹 *Італія — документи*\n\n✅ CMR накладна\n✅ Права CE + картка водія\n✅ Техпаспорт\n✅ Зелена картка\n💳 Autostrada платна\n\n🚫 Сб 14:00-22:00\n🚫 Нд 07:00-22:00\n⚠️ Зони ZTL у містах — штрафи!",
        "subscribe": "💎 *GidTrack Pro — 7€/місяць*\n\n🆓 Безкоштовно:\n• Ціни на пальне\n• 3 маршрути/місяць\n• Правила ЄС\n\n⭐ *Pro:*\n• Необмежені маршрути\n• Скан CMR → адреса → навігація\n• Стоянки TIR по маршруту\n• Сповіщення про заборони\n\n📩 @gidtrack_support",
    },
    "ru": {
        "welcome": "👋 Добро пожаловать в *GidTrack Bot*!\n\nТвой помощник дальнобойщика в Европе 🚛\n\nВыбери язык / Choose language:",
        "menu_title": "🚛 *Главное меню*",
        "route": "🗺️ Проложить маршрут",
        "fuel": "⛽ Цены на топливо",
        "border": "🛂 Документы на границу",
        "rules": "📋 Правила ЕС",
        "back": "◀️ Назад",
        "language": "🌍 Язык",
        "route_ask_from": "📍 *Откуда едешь?*\n\nНапиши город отправления:\n\nПримеры: _Lyon_, _Paris_, _Besançon_, _Milano_",
        "route_ask_to": "📍 *Куда едешь?*\n\nНапиши город назначения:",
        "route_ask_weight": "⚖️ *Полный вес грузовика:*",
        "w1": "до 7.5т",
        "w2": "7.5 — 12т",
        "w3": "12 — 40т",
        "searching": "🔍 Ищу маршрут...",
        "not_found": "❌ Город не найден. Проверь название и попробуй снова.\n\nПример: *Lyon*, *Munich*, *Roma*",
        "fuel_title": "⛽ *Цены на дизель сегодня*\n\n🟢 Самые дешёвые:\n🇧🇬 Болгария — 1.32€/л\n🇵🇱 Польша — 1.41€/л\n🇸🇰 Словакия — 1.48€/л\n\n🟡 Средние:\n🇫🇷 Франция — 1.65€/л\n🇩🇪 Германия — 1.71€/л\n🇦🇹 Австрия — 1.68€/л\n\n🔴 Самые дорогие:\n🇨🇭 Швейцария — 1.89€/л\n🇮🇹 Италия — 1.95€/л\n🇳🇱 Нидерланды — 2.05€/л\n\n_Обновлено сегодня_",
        "rules_text": "📋 *Правила водителя ЕС (рег. 561/2006)*\n\n⏱️ *Время вождения:*\n• День: макс. *9 часов* (2×/нед до 10ч)\n• Неделя: макс. *56 часов*\n• 2 недели: макс. *90 часов*\n\n😴 *Обязательный отдых:*\n• После 4.5ч — *45 минут*\n• Ежедневный — *11 часов*\n• Еженедельный — *45 часов*\n\n🚫 *Запреты движения:*\n🇫🇷 Пт 22:00 — Сб 22:00\n🇩🇪 Воскресенье + праздники\n🇮🇹 Сб 14:00 — Вс 22:00\n🇨🇭 Сб 15:00 — Вс 23:00",
        "border_ch": "🇨🇭 *Швейцария — документы*\n\n✅ CMR накладная\n✅ Права CE + карточка водителя\n✅ Техпаспорт\n✅ Зелёная карта\n✅ Виньетка 40 CHF ⚠️\n✅ Разрешение ЕКМТ\n\n📦 *Для груза:*\n• Декларация T1/T2\n• Санитарные сертификаты\n\n⚠️ Швейцария — не ЕС!\n🌙 Запрет 22:00-05:00\n🚫 Запрет в воскресенье",
        "border_de": "🇩🇪 *Германия — документы*\n\n✅ CMR накладная\n✅ Права CE + карточка водителя\n✅ Техпаспорт\n✅ Зелёная карта\n✅ Maut (toll-collect.de)\n\n⚠️ Maut обязателен для 7.5т+\n🚫 Запрет по воскресеньям\n🏙️ Минимум Euro 4 в городах",
        "border_it": "🇮🇹 *Италия — документы*\n\n✅ CMR накладная\n✅ Права CE + карточка водителя\n✅ Техпаспорт\n✅ Зелёная карта\n💳 Autostrada платная\n\n🚫 Сб 14:00-22:00\n🚫 Вс 07:00-22:00\n⚠️ Зоны ZTL в городах — штрафы!",
        "subscribe": "💎 *GidTrack Pro — 7€/месяц*\n\n🆓 Бесплатно:\n• Цены на топливо\n• 3 маршрута/месяц\n• Правила ЕС\n\n⭐ *Pro:*\n• Неограниченные маршруты\n• Скан CMR → адрес → навигация\n• Стоянки TIR по маршруту\n• Уведомления о запретах\n\n📩 @gidtrack_support",
    },
    "fr": {
        "welcome": "👋 Bienvenue sur *GidTrack Bot*!\n\nTon assistant chauffeur en Europe 🚛\n\nChoisis ta langue / Choose language:",
        "menu_title": "🚛 *Menu principal*",
        "route": "🗺️ Calculer un itinéraire",
        "fuel": "⛽ Prix du carburant",
        "border": "🛂 Documents frontière",
        "rules": "📋 Règles UE",
        "back": "◀️ Retour",
        "language": "🌍 Langue",
        "route_ask_from": "📍 *D'où pars-tu?*\n\nÉcris la ville de départ:\n\nExemples: _Lyon_, _Paris_, _Besançon_, _Milano_",
        "route_ask_to": "📍 *Où vas-tu?*\n\nÉcris la ville d'arrivée:",
        "route_ask_weight": "⚖️ *Poids total du camion:*",
        "w1": "jusqu'à 7.5t",
        "w2": "7.5 — 12t",
        "w3": "12 — 40t",
        "searching": "🔍 Calcul de l'itinéraire...",
        "not_found": "❌ Ville non trouvée. Vérifie le nom et réessaie.\n\nExemple: *Lyon*, *Munich*, *Roma*",
        "fuel_title": "⛽ *Prix du diesel aujourd'hui*\n\n🟢 Les moins chers:\n🇧🇬 Bulgarie — 1.32€/l\n🇵🇱 Pologne — 1.41€/l\n🇸🇰 Slovaquie — 1.48€/l\n\n🟡 Moyens:\n🇫🇷 France — 1.65€/l\n🇩🇪 Allemagne — 1.71€/l\n🇦🇹 Autriche — 1.68€/l\n\n🔴 Les plus chers:\n🇨🇭 Suisse — 1.89€/l\n🇮🇹 Italie — 1.95€/l\n🇳🇱 Pays-Bas — 2.05€/l\n\n_Mis à jour aujourd'hui_",
        "rules_text": "📋 *Règles UE (rèf. 561/2006)*\n\n⏱️ *Temps de conduite:*\n• Jour: max. *9h* (2×/sem jusqu'à 10h)\n• Semaine: max. *56h*\n• 2 semaines: max. *90h*\n\n😴 *Repos obligatoires:*\n• Après 4.5h — *45 min*\n• Quotidien — *11h*\n• Hebdomadaire — *45h*\n\n🚫 *Interdictions:*\n🇫🇷 Ven 22h — Sam 22h\n🇩🇪 Dimanche + fériés\n🇮🇹 Sam 14h — Dim 22h\n🇨🇭 Sam 15h — Dim 23h",
        "border_ch": "🇨🇭 *Suisse — documents*\n\n✅ Lettre de voiture CMR\n✅ Permis CE + carte conducteur\n✅ Carte grise\n✅ Carte Verte\n✅ Vignette 40 CHF ⚠️\n✅ Autorisation CEMT\n\n📦 *Pour la marchandise:*\n• Déclaration T1/T2\n• Certificats sanitaires\n\n⚠️ Suisse hors UE — douane!\n🌙 Interdiction 22h-05h\n🚫 Interdiction dimanche",
        "border_de": "🇩🇪 *Allemagne — documents*\n\n✅ Lettre de voiture CMR\n✅ Permis CE + carte conducteur\n✅ Carte grise\n✅ Carte Verte\n✅ Maut (toll-collect.de)\n\n⚠️ Maut obligatoire 7.5t+\n🚫 Interdiction dimanche\n🏙️ Euro 4 minimum en ville",
        "border_it": "🇮🇹 *Italie — documents*\n\n✅ Lettre de voiture CMR\n✅ Permis CE + carte conducteur\n✅ Carte grise\n✅ Carte Verte\n💳 Autostrade payantes\n\n🚫 Sam 14h-22h\n🚫 Dim 07h-22h\n⚠️ Zones ZTL en ville — amendes!",
        "subscribe": "💎 *GidTrack Pro — 7€/mois*\n\n🆓 Gratuit:\n• Prix carburant\n• 3 itinéraires/mois\n• Règles UE\n\n⭐ *Pro:*\n• Itinéraires illimités\n• Scan CMR → adresse → navigation\n• Parkings TIR sur le trajet\n• Alertes interdictions\n\n📩 @gidtrack_support",
    },
    "en": {
        "welcome": "👋 Welcome to *GidTrack Bot*!\n\nYour European truck driver assistant 🚛\n\nChoose language:",
        "menu_title": "🚛 *Main Menu*",
        "route": "🗺️ Calculate route",
        "fuel": "⛽ Fuel prices",
        "border": "🛂 Border documents",
        "rules": "📋 EU driving rules",
        "back": "◀️ Back",
        "language": "🌍 Language",
        "route_ask_from": "📍 *Where are you departing from?*\n\nType the departure city:\n\nExamples: _Lyon_, _Paris_, _Besançon_, _Milano_",
        "route_ask_to": "📍 *Where are you going?*\n\nType the destination city:",
        "route_ask_weight": "⚖️ *Total truck weight:*",
        "w1": "up to 7.5t",
        "w2": "7.5 — 12t",
        "w3": "12 — 40t",
        "searching": "🔍 Calculating route...",
        "not_found": "❌ City not found. Check the name and try again.\n\nExample: *Lyon*, *Munich*, *Roma*",
        "fuel_title": "⛽ *Diesel prices today*\n\n🟢 Cheapest:\n🇧🇬 Bulgaria — 1.32€/l\n🇵🇱 Poland — 1.41€/l\n🇸🇰 Slovakia — 1.48€/l\n\n🟡 Average:\n🇫🇷 France — 1.65€/l\n🇩🇪 Germany — 1.71€/l\n🇦🇹 Austria — 1.68€/l\n\n🔴 Most expensive:\n🇨🇭 Switzerland — 1.89€/l\n🇮🇹 Italy — 1.95€/l\n🇳🇱 Netherlands — 2.05€/l\n\n_Updated today_",
        "rules_text": "📋 *EU Driver Rules (reg. 561/2006)*\n\n⏱️ *Driving time:*\n• Day: max. *9h* (2×/week up to 10h)\n• Week: max. *56h*\n• 2 weeks: max. *90h*\n\n😴 *Mandatory rest:*\n• After 4.5h — *45 min*\n• Daily — *11h*\n• Weekly — *45h*\n\n🚫 *Driving bans:*\n🇫🇷 Fri 22:00 — Sat 22:00\n🇩🇪 Sunday + holidays\n🇮🇹 Sat 14:00 — Sun 22:00\n🇨🇭 Sat 15:00 — Sun 23:00",
        "border_ch": "🇨🇭 *Switzerland — documents*\n\n✅ CMR consignment note\n✅ CE license + driver card\n✅ Vehicle registration\n✅ Green Card insurance\n✅ Vignette 40 CHF ⚠️\n✅ ECMT permit\n\n📦 *For cargo:*\n• T1/T2 declaration\n• Health certificates\n\n⚠️ Switzerland not in EU!\n🌙 Ban 22:00-05:00\n🚫 Sunday driving ban",
        "border_de": "🇩🇪 *Germany — documents*\n\n✅ CMR consignment note\n✅ CE license + driver card\n✅ Vehicle registration\n✅ Green Card insurance\n✅ Maut (toll-collect.de)\n\n⚠️ Maut mandatory 7.5t+\n🚫 Sunday driving ban\n🏙️ Euro 4 minimum in cities",
        "border_it": "🇮🇹 *Italy — documents*\n\n✅ CMR consignment note\n✅ CE license + driver card\n✅ Vehicle registration\n✅ Green Card insurance\n💳 Autostrade toll roads\n\n🚫 Sat 14:00-22:00\n🚫 Sun 07:00-22:00\n⚠️ ZTL zones in cities — fines!",
        "subscribe": "💎 *GidTrack Pro — 7€/month*\n\n🆓 Free:\n• Fuel prices\n• 3 routes/month\n• EU rules\n\n⭐ *Pro:*\n• Unlimited routes\n• CMR scan → address → navigation\n• TIR parkings on route\n• Ban alerts\n\n📩 @gidtrack_support",
    }
}

user_data_store = {}

def get_lang(uid):
    return user_data_store.get(uid, {}).get("lang", "ru")

def t(uid, key):
    lang = get_lang(uid)
    return TEXTS.get(lang, TEXTS["ru"]).get(key, key)

def set_step(uid, step):
    if uid not in user_data_store:
        user_data_store[uid] = {}
    user_data_store[uid]["step"] = step

def get_step(uid):
    return user_data_store.get(uid, {}).get("step", "")

async def geocode(city_name):
    """Get coordinates for a city using Nominatim (free, no key needed)"""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": city_name, "format": "json", "limit": 1}
        headers = {"User-Agent": "GidTrackBot/1.0"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data:
                    return float(data[0]["lon"]), float(data[0]["lat"]), data[0]["display_name"]
    except Exception as e:
        logger.error(f"Geocode error: {e}")
    return None, None, None

async def get_route(lon1, lat1, lon2, lat2):
    """Get route distance and duration using OSRM (free, no key needed)"""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
        params = {"overview": "false", "steps": "false"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                if data.get("code") == "Ok":
                    route = data["routes"][0]
                    km = round(route["distance"] / 1000)
                    mins = round(route["duration"] / 60)
                    hours = mins // 60
                    minutes = mins % 60
                    return km, f"{hours}h{minutes:02d}"
    except Exception as e:
        logger.error(f"Route error: {e}")
    return None, None

def estimate_countries(city_from, city_to):
    """Simple country estimation based on city names for toll calculation"""
    fr_cities = ["paris", "lyon", "marseille", "toulouse", "nice", "besancon", "strasbourg", "bordeaux", "lille", "nantes", "montpellier", "dijon", "grenoble", "rennes", "metz", "nancy", "reims", "angers", "caen", "tours"]
    de_cities = ["berlin", "munich", "hamburg", "cologne", "frankfurt", "stuttgart", "dusseldorf", "dortmund", "essen", "bremen", "hannover", "nuremberg", "leipzig", "dresden", "bonn"]
    it_cities = ["rome", "roma", "milan", "milano", "naples", "napoli", "turin", "torino", "palermo", "genoa", "genova", "bologna", "florence", "firenze", "venice", "venezia", "verona", "trieste"]
    ch_cities = ["zurich", "bern", "geneva", "geneve", "lausanne", "basel", "bale", "lugano", "lucerne", "luzern", "st. gallen", "winterthur"]
    es_cities = ["madrid", "barcelona", "valencia", "seville", "sevilla", "zaragoza", "malaga", "bilbao", "alicante", "cordoba", "valladolid", "vigo"]
    pl_cities = ["warsaw", "warszawa", "krakow", "lodz", "wroclaw", "poznan", "gdansk", "szczecin", "bydgoszcz", "lublin"]
    be_cities = ["brussels", "bruxelles", "antwerp", "anvers", "ghent", "gand", "bruges", "liege", "namur"]
    at_cities = ["vienna", "wien", "graz", "linz", "salzburg", "innsbruck", "klagenfurt"]
    nl_cities = ["amsterdam", "rotterdam", "the hague", "den haag", "utrecht", "eindhoven", "tilburg", "groningen"]

    def get_country(city):
        c = city.lower()
        if any(x in c for x in fr_cities): return "FR"
        if any(x in c for x in de_cities): return "DE"
        if any(x in c for x in it_cities): return "IT"
        if any(x in c for x in ch_cities): return "CH"
        if any(x in c for x in es_cities): return "ES"
        if any(x in c for x in pl_cities): return "PL"
        if any(x in c for x in be_cities): return "BE"
        if any(x in c for x in at_cities): return "AT"
        if any(x in c for x in nl_cities): return "NL"
        return "EU"

    return get_country(city_from), get_country(city_to)

def calc_cost(km, city_from, city_to, weight_t):
    """Calculate trip cost"""
    c_from, c_to = estimate_countries(city_from, city_to)
    fuel_price = FUEL_PRICES.get(c_from, 1.65)
    if weight_t <= 7.5:
        consumption = 25
    elif weight_t <= 12:
        consumption = 28
    else:
        consumption = 32
    fuel_liters = round(km * consumption / 100)
    fuel_cost = round(fuel_liters * fuel_price)
    toll_from = TOLL_PER_100KM.get(c_from, 3.0)
    toll_to = TOLL_PER_100KM.get(c_to, 3.0)
    avg_toll = (toll_from + toll_to) / 2
    toll_cost = round(km * avg_toll / 100)
    ch_cost = 0
    if c_from == "CH" or c_to == "CH":
        ch_cost = CH_VIGNETTE
        toll_cost = 0
    total = fuel_cost + toll_cost + ch_cost
    return fuel_liters, fuel_cost, fuel_price, toll_cost, ch_cost, total, c_from, c_to

def lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"),
         InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ])

def main_menu_keyboard(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "route"), callback_data="menu_route")],
        [InlineKeyboardButton(t(uid, "fuel"), callback_data="menu_fuel"),
         InlineKeyboardButton(t(uid, "rules"), callback_data="menu_rules")],
        [InlineKeyboardButton(t(uid, "border"), callback_data="menu_border")],
        [InlineKeyboardButton("💎 Pro", callback_data="menu_subscribe"),
         InlineKeyboardButton(t(uid, "language"), callback_data="menu_lang")]
    ])

def back_keyboard(uid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t(uid, "back"), callback_data="back_main")]])

def weight_keyboard(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(uid, "w1"), callback_data="weight_7"),
         InlineKeyboardButton(t(uid, "w2"), callback_data="weight_12")],
        [InlineKeyboardButton(t(uid, "w3"), callback_data="weight_40")],
        [InlineKeyboardButton(t(uid, "back"), callback_data="back_main")]
    ])

def border_keyboard(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇨🇭 Швейцария / Suisse / Switzerland", callback_data="border_ch")],
        [InlineKeyboardButton("🇩🇪 Германия / Allemagne / Germany", callback_data="border_de")],
        [InlineKeyboardButton("🇮🇹 Италия / Italie / Italy", callback_data="border_it")],
        [InlineKeyboardButton(t(uid, "back"), callback_data="back_main")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        TEXTS["ru"]["welcome"],
        reply_markup=lang_keyboard(),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data.startswith("lang_"):
        lang = data.split("_")[1]
        if uid not in user_data_store:
            user_data_store[uid] = {}
        user_data_store[uid]["lang"] = lang
        await query.edit_message_text(
            t(uid, "menu_title"),
            reply_markup=main_menu_keyboard(uid),
            parse_mode="Markdown"
        )
    elif data in ("back_main", "menu_lang"):
        if data == "menu_lang":
            await query.edit_message_text(t(uid, "welcome"), reply_markup=lang_keyboard(), parse_mode="Markdown")
        else:
            set_step(uid, "")
            await query.edit_message_text(t(uid, "menu_title"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown")
    elif data == "menu_fuel":
        await query.edit_message_text(t(uid, "fuel_title"), reply_markup=back_keyboard(uid), parse_mode="Markdown")
    elif data == "menu_rules":
        await query.edit_message_text(t(uid, "rules_text"), reply_markup=back_keyboard(uid), parse_mode="Markdown")
    elif data == "menu_subscribe":
        await query.edit_message_text(t(uid, "subscribe"), reply_markup=back_keyboard(uid), parse_mode="Markdown")
    elif data == "menu_border":
        await query.edit_message_text(t(uid, "border_ask") if "border_ask" in TEXTS["ru"] else "🛂 Выбери страну:", reply_markup=border_keyboard(uid), parse_mode="Markdown")
    elif data.startswith("border_"):
        country = data.split("_")[1]
        key = f"border_{country}"
        await query.edit_message_text(t(uid, key), reply_markup=back_keyboard(uid), parse_mode="Markdown")
    elif data == "menu_route":
        if uid not in user_data_store:
            user_data_store[uid] = {}
        set_step(uid, "from")
        await query.edit_message_text(t(uid, "route_ask_from"), reply_markup=back_keyboard(uid), parse_mode="Markdown")
    elif data.startswith("weight_"):
        w_map = {"weight_7": 7.5, "weight_12": 12, "weight_40": 40}
        weight = w_map.get(data, 40)
        if uid not in user_data_store:
            user_data_store[uid] = {}
        user_data_store[uid]["weight"] = weight
        city_from = user_data_store[uid].get("from", "")
        city_to = user_data_store[uid].get("to", "")
        await query.edit_message_text(t(uid, "searching"), parse_mode="Markdown")
        lon1, lat1, name1 = await geocode(city_from)
        lon2, lat2, name2 = await geocode(city_to)
        if not lon1 or not lon2:
            await query.edit_message_text(t(uid, "not_found"), reply_markup=back_keyboard(uid), parse_mode="Markdown")
            return
        km, duration = await get_route(lon1, lat1, lon2, lat2)
        if not km:
            await query.edit_message_text(t(uid, "not_found"), reply_markup=back_keyboard(uid), parse_mode="Markdown")
            return
        fuel_l, fuel_cost, fuel_price, toll_cost, ch_cost, total, c_from, c_to = calc_cost(km, city_from, city_to, weight)
        lang = get_lang(uid)
        city_f = city_from.title()
        city_t = city_to.title()
        if lang == "uk":
            lines = [
                f"✅ *{city_f} → {city_t}*\n",
                f"📏 Відстань: *{km} км*",
                f"⏱️ Час: ~*{duration}*\n",
                f"*Витрати:*",
                f"⛽ Пальне: {fuel_l}л × {fuel_price}€ = *{fuel_cost}€*",
            ]
        elif lang == "fr":
            lines = [
                f"✅ *{city_f} → {city_t}*\n",
                f"📏 Distance: *{km} km*",
                f"⏱️ Durée: ~*{duration}*\n",
                f"*Coûts:*",
                f"⛽ Carburant: {fuel_l}l × {fuel_price}€ = *{fuel_cost}€*",
            ]
        elif lang == "en":
            lines = [
                f"✅ *{city_f} → {city_t}*\n",
                f"📏 Distance: *{km} km*",
                f"⏱️ Time: ~*{duration}*\n",
                f"*Costs:*",
                f"⛽ Fuel: {fuel_l}l × {fuel_price}€ = *{fuel_cost}€*",
            ]
        else:
            lines = [
                f"✅ *{city_f} → {city_t}*\n",
                f"📏 Расстояние: *{km} км*",
                f"⏱️ Время: ~*{duration}*\n",
                f"*Стоимость:*",
                f"⛽ Топливо: {fuel_l}л × {fuel_price}€ = *{fuel_cost}€*",
            ]
        if ch_cost > 0:
            lines.append(f"🇨🇭 Виньетка CH: *{ch_cost}€*")
        elif toll_cost > 0:
            if lang == "uk": lines.append(f"🛣️ Дороги/збори: *{toll_cost}€*")
            elif lang == "fr": lines.append(f"🛣️ Péages: *{toll_cost}€*")
            elif lang == "en": lines.append(f"🛣️ Tolls: *{toll_cost}€*")
            else: lines.append(f"🛣️ Дороги/сборы: *{toll_cost}€*")
        lines.append(f"\n{'━'*18}")
        if lang == "uk": lines.append(f"💰 *Разом: {total}€*")
        elif lang == "fr": lines.append(f"💰 *Total: {total}€*")
        elif lang == "en": lines.append(f"💰 *Total: {total}€*")
        else: lines.append(f"💰 *Итого: {total}€*")
        if lang == "uk": lines.append(f"\n💡 _Заправся перед виїздом у {c_from}!_")
        elif lang == "fr": lines.append(f"\n💡 _Fais le plein avant de partir depuis {c_from}!_")
        elif lang == "en": lines.append(f"\n💡 _Fill up before departure in {c_from}!_")
        else: lines.append(f"\n💡 _Заправься перед выездом в {c_from}!_")
        result = "\n".join(lines)
        route_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Новый маршрут" if lang=="ru" else "🔄 New route" if lang=="en" else "🔄 Nouvel itinéraire" if lang=="fr" else "🔄 Новий маршрут", callback_data="menu_route")],
            [InlineKeyboardButton(t(uid, "back"), callback_data="back_main")]
        ])
        await query.edit_message_text(result, reply_markup=route_kb, parse_mode="Markdown")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    step = get_step(uid)
    if step == "from":
        user_data_store[uid]["from"] = text
        set_step(uid, "to")
        await update.message.reply_text(t(uid, "route_ask_to"), reply_markup=back_keyboard(uid), parse_mode="Markdown")
    elif step == "to":
        user_data_store[uid]["to"] = text
        set_step(uid, "weight")
        await update.message.reply_text(t(uid, "route_ask_weight"), reply_markup=weight_keyboard(uid), parse_mode="Markdown")
    else:
        await update.message.reply_text(t(uid, "menu_title"), reply_markup=main_menu_keyboard(uid), parse_mode="Markdown")

def main():
    if not TOKEN:
        logger.error("BOT_TOKEN not set!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    logger.info("GidTrack Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()                
