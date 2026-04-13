import os, logging, aiohttp, re, base64, math
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ─────────────────────────────────────────────────────
TOKEN      = os.environ.get("BOT_TOKEN", "")
OCR_KEY    = os.environ.get("OCR_KEY", "")
ORS_KEY    = os.environ.get("ORS_API_KEY", "")
TOMTOM_KEY = os.environ.get("TOMTOM_KEY", "")

# ─── СПРАВОЧНИКИ ─────────────────────────────────────────────────────────────
DIESEL = {
    "FR":1.65,"DE":1.71,"IT":1.95,"CH":1.89,"ES":1.55,"BE":1.68,
    "NL":2.05,"AT":1.68,"PL":1.41,"CZ":1.52,"SK":1.48,"HU":1.44,
    "RO":1.38,"BG":1.32,"UA":0.95,"LU":1.48,"SI":1.55,"HR":1.42,
    "RS":1.38,"BA":1.35,"AL":1.50,"MK":1.40,"ME":1.45,"GR":1.78,
}
TOLL = {
    "FR":25.0,"DE":19.0,"IT":18.0,"ES":15.0,"AT":26.0,
    "PL":12.0,"CZ":14.0,"HU":18.0,"BE":15.0,"SI":14.0,
    "HR":16.0,"GR":10.0,"RO":8.0,"BG":6.0,"SK":10.0,
}
CH_VIGNETTE = 42

# Коды погоды WMO → описание
WEATHER_CODES = {
    0:"ясно", 1:"в основном ясно", 2:"переменная облачность", 3:"пасмурно",
    45:"туман", 48:"туман с инеем",
    51:"лёгкая морось", 53:"морось", 55:"сильная морось",
    61:"лёгкий дождь", 63:"дождь", 65:"сильный дождь",
    71:"лёгкий снег", 73:"снег", 75:"сильный снег",
    77:"снежная крупа",
    80:"ливни", 81:"сильные ливни", 82:"очень сильные ливни",
    85:"снежные ливни", 86:"сильные снежные ливни",
    95:"гроза", 96:"гроза с градом", 99:"сильная гроза с градом",
}
WEATHER_CODES_FR = {
    0:"dégagé", 1:"peu nuageux", 2:"partiellement nuageux", 3:"couvert",
    45:"brouillard", 48:"brouillard givrant",
    51:"bruine légère", 53:"bruine", 55:"bruine forte",
    61:"pluie légère", 63:"pluie", 65:"pluie forte",
    71:"neige légère", 73:"neige", 75:"forte neige",
    80:"averses", 81:"fortes averses", 95:"orage", 99:"orage avec grêle",
}
WEATHER_CODES_EN = {
    0:"clear", 1:"mostly clear", 2:"partly cloudy", 3:"overcast",
    45:"fog", 48:"icy fog",
    51:"light drizzle", 53:"drizzle", 55:"heavy drizzle",
    61:"light rain", 63:"rain", 65:"heavy rain",
    71:"light snow", 73:"snow", 75:"heavy snow",
    80:"showers", 81:"heavy showers", 95:"thunderstorm", 99:"severe thunderstorm",
}

EMERGENCY = {
    "FR":{"police":"17","ambulance":"15","fire":"18","eu":"112","road":"0800 207 207","info":"SAMU=15, autoroutes VINCI"},
    "DE":{"police":"110","ambulance":"112","fire":"112","eu":"112","road":"0800 5 00 40 35","info":"ADAC Pannenhilfe"},
    "IT":{"police":"113","ambulance":"118","fire":"115","eu":"112","road":"803 116","info":"ACI soccorso"},
    "CH":{"police":"117","ambulance":"144","fire":"118","eu":"112","road":"140","info":"TCS Pannenhilfe"},
    "AT":{"police":"133","ambulance":"144","fire":"122","eu":"112","road":"120","info":"ÖAMTC"},
    "PL":{"police":"997","ambulance":"999","fire":"998","eu":"112","road":"19637","info":"PZMot pomoc drogowa"},
    "BE":{"police":"101","ambulance":"100","fire":"100","eu":"112","road":"0800 14 595","info":"Touring assistance"},
    "NL":{"police":"112","ambulance":"112","fire":"112","eu":"112","road":"088 269 2888","info":"ANWB hulp"},
    "ES":{"police":"091","ambulance":"061","fire":"080","eu":"112","road":"900 123 505","info":"DGT"},
    "CZ":{"police":"158","ambulance":"155","fire":"150","eu":"112","road":"1240","info":"ÚAMK"},
    "HU":{"police":"107","ambulance":"104","fire":"105","eu":"112","road":"+36 188","info":"Magyar Autóklub"},
    "RO":{"police":"112","ambulance":"112","fire":"112","eu":"112","road":"9271","info":"ACR"},
}

BANS = {
    "FR":["Пятница 22:00 — Суббота 22:00","Суббота перед праздником 22:00 — Воскресенье 22:00","1 янв, 8 май, 14 июл, 15 авг, 1 ноя, 25 дек — весь день"],
    "DE":["Воскресенье 00:00 — 22:00","Праздничные дни 00:00 — 22:00"],
    "IT":["Суббота 14:00—22:00 (лето 08:00-22:00)","Воскресенье 07:00 — 22:00","Канун праздников"],
    "CH":["Суббота 15:00 — Воскресенье 23:00","Праздники 00:00 — 23:00","Ночной запрет 22:00—05:00 каждый день!"],
    "AT":["Воскресенье 00:00 — 22:00","Праздники 00:00 — 22:00"],
    "PL":["Пятница 18:00 — Воскресенье 22:00 (лето)","Суббота 08:00 — Воскресенье 22:00 (зима)"],
    "BE":["Суббота 22:00 — Воскресенье 22:00"],
    "ES":["Пятница 14:00 — Понедельник 00:00 (лето)","Воскресенье 07:00—22:00"],
}

BORDER = {
"CH":{
    "ru":"*ШВЕЙЦАРИЯ*\n\n• CMR накладная\n• Права CE + карточка водителя\n• Техпаспорт + Зелёная карта\n• Виньетка 40 CHF (обязательно!)\n• Разрешение ЕКМТ\n\nТаможня обязательна!\nЗапрет: ночь 22:00—05:00, воскресенье",
    "fr":"*SUISSE*\n\n• CMR\n• Permis CE + carte conducteur\n• Carte grise + Carte Verte\n• Vignette 40 CHF (obligatoire!)\n• Autorisation CEMT\n\nDouane obligatoire!\nInterdiction: nuit 22h—05h, dimanche",
    "en":"*SWITZERLAND*\n\n• CMR consignment note\n• CE license + driver card\n• Registration + Green Card\n• Vignette 40 CHF (mandatory!)\n• ECMT permit\n\nCustoms required!\nBan: night 22:00—05:00, Sunday",
    "uk":"*ШВЕЙЦАРІЯ*\n\n• CMR накладна\n• Права CE + карточка водія\n• Техпаспорт + Зелена картка\n• Víньєтка 40 CHF (обов'язково!)\n• Дозвіл ЄКМТ\n\nМитниця обов'язкова!\nЗаборона: ніч 22:00—05:00, неділя",
},
"DE":{
    "ru":"*ГЕРМАНИЯ*\n\n• CMR накладная\n• Права CE + карточка водителя\n• Техпаспорт + Зелёная карта\n• Maut toll-collect.de (обязателен 7.5т+!)\n\nЗапрет: Вс 00:00—22:00 + праздники\nEuro 4+ в зонах LEZ",
    "fr":"*ALLEMAGNE*\n\n• CMR\n• Permis CE + carte conducteur\n• Carte grise + Carte Verte\n• Maut toll-collect.de (obligatoire 7.5t+!)\n\nInterdiction: dim 00h—22h + fériés",
    "en":"*GERMANY*\n\n• CMR note\n• CE license + driver card\n• Registration + Green Card\n• Maut toll-collect.de (mandatory 7.5t+!)\n\nBan: Sun 00:00—22:00 + holidays",
    "uk":"*НIМЕЧЧИНА*\n\n• CMR накладна\n• Права CE + карточка водія\n• Техпаспорт + Зелена картка\n• Maut toll-collect.de (обов'язковий 7.5т+!)\n\nЗаборона: нд 00:00—22:00 + свята",
},
"IT":{
    "ru":"*ИТАЛИЯ*\n\n• CMR накладная\n• Права CE + карточка водителя\n• Техпаспорт + Зелёная карта\n• Autostrada — платные дороги\n\nЗапрет: Сб 14:00—22:00, Вс 07:00—22:00\nЗоны ZTL в городах — штрафы!",
    "fr":"*ITALIE*\n\n• CMR\n• Permis CE + carte conducteur\n• Carte grise + Carte Verte\n• Autostrade payantes\n\nInterdiction: Sam 14h—22h, Dim 07h—22h\nZones ZTL — amendes!",
    "en":"*ITALY*\n\n• CMR note\n• CE license + driver card\n• Registration + Green Card\n• Autostrade toll roads\n\nBan: Sat 14:00—22:00, Sun 07:00—22:00\nZTL zones — fines!",
    "uk":"*IТАЛІЯ*\n\n• CMR накладна\n• Права CE + карточка водія\n• Техпаспорт + Зелена картка\n• Autostrada — платні дороги\n\nЗаборона: Сб 14:00—22:00, Нд 07:00—22:00\nЗони ZTL — штрафи!",
},
"FR":{
    "ru":"*ФРАНЦИЯ*\n\n• CMR накладная\n• Права CE + карточка водителя\n• Техпаспорт + Зелёная карта\n• Péage — платные дороги\n• Crit'Air виньетка (городские зоны)\n\nЗапрет: Пт 22:00—Сб 22:00",
    "fr":"*FRANCE*\n\n• CMR\n• Permis CE + carte conducteur\n• Carte grise + Carte Verte\n• Péages automatiques\n• Vignette Crit'Air en ville\n\nInterdiction: Ven 22h—Sam 22h",
    "en":"*FRANCE*\n\n• CMR note\n• CE license + driver card\n• Registration + Green Card\n• Péage toll roads\n• Crit'Air vignette in cities\n\nBan: Fri 22:00—Sat 22:00",
    "uk":"*ФРАНЦІЯ*\n\n• CMR накладна\n• Права CE + карточка водія\n• Техпаспорт + Зелена картка\n• Péage — платні дороги\n• Crit'Air у містах\n\nЗаборона: Пт 22:00—Сб 22:00",
},
"AT":{
    "ru":"*АВСТРИЯ*\n\n• CMR накладная\n• Права CE + карточка водителя\n• Техпаспорт + Зелёная карта\n• Maut go-maut.at (для 3.5т+)\n• ЕКМТ или двустороннее разрешение\n\nЗапрет: Вс 00:00—22:00\nНочное ограничение 80 км/ч",
    "fr":"*AUTRICHE*\n\n• CMR\n• Permis CE + carte conducteur\n• Carte grise + Carte Verte\n• Maut go-maut.at (3.5t+)\n\nInterdiction: dim 00h—22h",
    "en":"*AUSTRIA*\n\n• CMR note\n• CE license + driver card\n• Registration + Green Card\n• Maut go-maut.at (3.5t+)\n\nBan: Sun 00:00—22:00\nNight limit 80 km/h",
    "uk":"*АВСТРІЯ*\n\n• CMR накладна\n• Права CE + карточка водія\n• Техпаспорт + Зелена картка\n• Maut go-maut.at (для 3.5т+)\n\nЗаборона: нд 00:00—22:00",
},
"PL":{
    "ru":"*ПОЛЬША*\n\n• CMR накладная\n• Права CE + карточка водителя\n• Техпаспорт + Зелёная карта\n• e-TOLL etoll.gov.pl (обязателен!)\n\nЗапрет: Пт 18:00—Вс 22:00 (лето)\nviaTOLL отменён — только e-TOLL!",
    "fr":"*POLOGNE*\n\n• CMR\n• Permis CE + carte conducteur\n• Carte grise + Carte Verte\n• e-TOLL etoll.gov.pl (obligatoire!)\n\nInterdiction: Ven 18h—Dim 22h (été)",
    "en":"*POLAND*\n\n• CMR note\n• CE license + driver card\n• Registration + Green Card\n• e-TOLL etoll.gov.pl (mandatory!)\n\nBan: Fri 18:00—Sun 22:00 (summer)",
    "uk":"*ПОЛЬЩА*\n\n• CMR накладна\n• Права CE + карточка водія\n• Техпаспорт + Зелена картка\n• e-TOLL etoll.gov.pl (обов'язковий!)\n\nЗаборона: Пт 18:00—Нд 22:00 (літо)",
},
}

RATES_EUR = {
    "CHF":0.93,"PLN":4.26,"CZK":25.1,"HUF":395.0,"RON":4.97,
    "BGN":1.96,"GBP":1.17,"UAH":43.5,"NOK":11.8,"SEK":11.4,"USD":1.08,
}

def get_cons(w):
    if w<=7.5: return 18.0
    elif w<=12: return 22.0
    elif w<=20: return 28.0
    elif w<=30: return 31.0
    return 34.0

def haversine(lat1, lon1, lat2, lon2):
    """Расстояние между двумя координатами в км"""
    R = 6371
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def interpolate_points(lat1, lon1, lat2, lon2, step_km=250):
    """Генерирует промежуточные точки по маршруту каждые step_km км"""
    total = haversine(lat1, lon1, lat2, lon2)
    if total <= step_km:
        return [(lat2, lon2)]
    points = []
    n = max(1, int(total / step_km))
    for i in range(1, n+1):
        t = i / n
        lat = lat1 + t*(lat2-lat1)
        lon = lon1 + t*(lon2-lon1)
        points.append((lat, lon))
    return points

udata = {}
def ud(uid):
    if uid not in udata:
        udata[uid] = {
            "lang":"ru","step":"","from":"","to":"","weight":20.0,
            "tacho_start":None,"tacho_daily":0.0,"tacho_weekly":0.0,
        }
    return udata[uid]

# ─── ТЕКСТЫ ──────────────────────────────────────────────────────────────────
T = {
"ru":{
    "welcome":"Привет! Я *GidTrack Navigator* — умный навигатор и помощник дальнобойщика!\n\nПрокладываю маршрут и сразу нахожу:\n• Пробки и инциденты на пути\n• Стоянки TIR вдоль маршрута\n• Погоду в ключевых точках\n• Полную стоимость рейса\n\nВыбери язык:",
    "menu":"Главное меню GidTrack Navigator",
    "r_route":"Маршрут + навигация","r_fuel":"Цены на дизель",
    "r_parking":"Стоянки TIR","r_tacho":"Тахограф",
    "r_border":"Документы / Границы","r_bans":"Запреты движения",
    "r_emergency":"Экстренные номера","r_currency":"Конвертер валют",
    "r_cmr":"Скан CMR","r_rules":"Правила ЕС",
    "r_lang":"Язык","r_pro":"Pro подписка","r_back":"Назад",
    "ask_from":"Откуда едешь?\n\nНапиши город отправления:\n_Lyon, Berlin, Besancon, Warsaw, Milano_",
    "ask_to":"Куда едешь?\n\nНапиши город назначения:",
    "ask_w":"Полный вес грузовика (брутто тонн):",
    "w1":"до 7.5т","w2":"7.5—12т","w3":"12—20т","w4":"20—40т",
    "searching":"Прокладываю маршрут...\nПроверяю пробки и ищу стоянки TIR по пути...",
    "not_found":"Город не найден. Проверь название.\n\nПример: *Lyon*, *Berlin*, *Milano*",
    "ask_parking":"Напиши город или отправь геолокацию — найду ближайшие стоянки TIR:",
    "search_parking":"Ищу стоянки TIR...",
    "no_parking":"Стоянки TIR не найдены в радиусе 60 км.",
    "ask_emergency":"Выбери страну для экстренных номеров:",
    "ask_bans":"Выбери страну для запретов движения:",
    "ask_currency":"Напиши сумму и валюту:\n_Пример: 100 CHF или 500 PLN_",
    "tacho_menu":"Таймер тахографа (Рег. ЕС 561/2006):",
    "tacho_start_btn":"Старт вождения","tacho_stop_btn":"Остановка",
    "tacho_status_btn":"Статус","tacho_reset_btn":"Сброс (новая неделя)",
    "tacho_started":"Таймер запущен!\n\nЕС 561/2006:\n• Максимум без перерыва: *4.5 ч*\n• Обязательный перерыв: *45 мин*\n• Максимум за день: *9 ч*\n• Максимум за неделю: *56 ч*",
    "tacho_already":"Таймер уже запущен! Сначала нажми Остановка.",
    "tacho_stopped":"Остановка зафиксирована.",
    "tacho_not_started":"Таймер не запущен. Нажми Старт вождения.",
    "ask_cmr":"Отправь фото CMR накладной.\nЯ прочитаю адрес выгрузки и построю маршрут.",
    "ocr_proc":"Читаю документ...","ocr_nokey":"OCR недоступен. Добавь OCR_KEY в Railway.",
    "new_route":"Новый маршрут","addr_found":"Адрес из CMR",
    "addr_none":"Адрес не найден. Введи вручную.","cmr_raw":"Текст CMR",
    "lbl_hgv":"Грузовой маршрут (ORS-HGV)","lbl_std":"Стандартный маршрут (OSRM)",
    "lbl_dist":"Расстояние","lbl_time":"Время в пути",
    "lbl_weight":"Вес","lbl_cons":"Расход",
    "lbl_fuel":"Топливо","lbl_toll":"Платные дороги",
    "lbl_vign":"Виньетка CH","lbl_total":"ИТОГО",
    "lbl_tip":"Совет: заправься в","lbl_save":"экономия",
    "lbl_traffic":"Пробки по маршруту","lbl_parkings":"Стоянки TIR по маршруту",
    "lbl_weather":"Погода по маршруту","lbl_no_traffic":"Пробок нет — дорога свободна",
    "lbl_no_tomtom":"(добавь TOMTOM_KEY для проверки пробок)",
    "fuel_prices":(
        "*Цены на дизель по Европе*\n\n"
        "Самые дешёвые:\n"
        "Украина — 0.95€/л\nБолгария — 1.32€/л\nРумыния — 1.38€/л\n"
        "Польша — 1.41€/л\nСловакия — 1.48€/л\nЛюксембург — 1.48€/л\n\n"
        "Средние:\nХорватия — 1.42€/л\nИспания — 1.55€/л\nЧехия — 1.52€/л\n"
        "Франция — 1.65€/л\nАвстрия — 1.68€/л\nГермания — 1.71€/л\n\n"
        "Дорогие:\nШвейцария — 1.89€/л\nИталия — 1.95€/л\nНидерланды — 2.05€/л\n\n"
        "Совет: заправляйся в Польше или Люксембурге — экономия до 80€ на рейсе!"
    ),
    "rules_text":(
        "*Режим труда и отдыха ЕС (Рег. 561/2006)*\n\n"
        "*Вождение:*\n"
        "• День: до 9 ч (2× в нед. можно 10 ч)\n"
        "• Неделя: до 56 ч\n• 2 недели: до 90 ч\n\n"
        "*Отдых:*\n• После 4.5 ч — 45 мин перерыв\n"
        "• Ежедневный — 11 ч (3× в нед. можно 9 ч)\n"
        "• Еженедельный — 45 ч (сокр. 24 ч)\n\n"
        "*Запреты движения:*\n"
        "Франция: Пт 22:00—Сб 22:00\nГермания: Вс + праздники\n"
        "Италия: Сб 14:00—Вс 22:00\nШвейцария: Сб 15:00—Вс 23:00\n"
        "Австрия: Вс 00:00—22:00\nПольша: Пт 18:00—Вс 22:00 (лето)"
    ),
    "b_ask":"Выбери страну для проверки документов:",
    "pro_text":(
        "*GidTrack Navigator Pro — 7€/месяц*\n\n"
        "Бесплатно: 3 маршрута, дизель, правила\n\n"
        "Pro — всё включено:\n"
        "• Неограниченные маршруты HGV\n"
        "• Пробки TomTom по маршруту\n"
        "• Стоянки TIR вдоль пути\n"
        "• Погода по контрольным точкам\n"
        "• Таймер тахографа с уведомлениями\n"
        "• Скан CMR накладных\n"
        "• Экстренные номера 12 стран\n"
        "• Конвертер 15 валют\n"
        "• Запреты движения\n"
        "• Поддержка 24/7\n\n"
        "Оформить: @gidtrack_support"
    ),
    "help_text":(
        "*GidTrack Navigator — команды:*\n\n"
        "/start — главное меню\n"
        "/route — маршрут с пробками и стоянками\n"
        "/parking — стоянки TIR рядом\n"
        "/tacho — таймер тахографа\n"
        "/fuel — цены на дизель\n"
        "/bans — запреты движения\n"
        "/emergency — экстренные номера\n"
        "/currency — конвертер валют\n"
        "/rules — правила ЕС\n"
        "/help — эта справка"
    ),
},
"fr":{
    "welcome":"Bonjour! Je suis *GidTrack Navigator* — ton navigateur et assistant chauffeur!\n\nJe calcule l'itinéraire et trouve:\n• Trafic et incidents en route\n• Parkings TIR le long du trajet\n• Météo aux points clés\n• Coût total du trajet\n\nChoisis ta langue:",
    "menu":"Menu GidTrack Navigator",
    "r_route":"Itinéraire + navigation","r_fuel":"Prix diesel",
    "r_parking":"Parkings TIR","r_tacho":"Tachygraphe",
    "r_border":"Documents / Frontières","r_bans":"Interdictions",
    "r_emergency":"Urgences","r_currency":"Devises",
    "r_cmr":"Scanner CMR","r_rules":"Règles UE",
    "r_lang":"Langue","r_pro":"Abonnement Pro","r_back":"Retour",
    "ask_from":"Ville de départ:\n_Lyon, Berlin, Besancon, Milano_",
    "ask_to":"Ville d'arrivée:",
    "ask_w":"Poids total du camion (PTC tonnes):",
    "w1":"7.5t","w2":"7.5—12t","w3":"12—20t","w4":"20—40t",
    "searching":"Calcul de l'itinéraire...\nVérification du trafic et recherche des parkings TIR...",
    "not_found":"Ville non trouvée. Vérifie le nom.",
    "ask_parking":"Ecris une ville ou envoie ta position — je trouve les parkings TIR:",
    "search_parking":"Recherche parkings TIR...","no_parking":"Aucun parking TIR trouvé dans 60 km.",
    "ask_emergency":"Choisis le pays:","ask_bans":"Choisis le pays pour les interdictions:",
    "ask_currency":"Montant et devise:\n_Exemple: 100 CHF ou 500 PLN_",
    "tacho_menu":"Minuteur tachygraphe (Règl. UE 561/2006):",
    "tacho_start_btn":"Démarrer conduite","tacho_stop_btn":"Arrêt",
    "tacho_status_btn":"Statut","tacho_reset_btn":"Réinitialiser",
    "tacho_started":"Minuteur démarré!\n\nRègl. UE 561/2006:\n• Max sans pause: *4.5h*\n• Pause obligatoire: *45 min*\n• Max par jour: *9h*\n• Max par semaine: *56h*",
    "tacho_already":"Minuteur déjà démarré! Appuie sur Arrêt d'abord.",
    "tacho_stopped":"Arrêt enregistré.","tacho_not_started":"Minuteur non démarré.",
    "ask_cmr":"Envoie une photo CMR. Je lirai l'adresse de livraison.",
    "ocr_proc":"Lecture...","ocr_nokey":"OCR indisponible. Ajoute OCR_KEY dans Railway.",
    "new_route":"Nouvel itinéraire","addr_found":"Adresse CMR",
    "addr_none":"Adresse non trouvée. Saisis manuellement.","cmr_raw":"Texte CMR",
    "lbl_hgv":"Itinéraire PL (ORS-HGV)","lbl_std":"Itinéraire standard (OSRM)",
    "lbl_dist":"Distance","lbl_time":"Durée",
    "lbl_weight":"Poids","lbl_cons":"Conso",
    "lbl_fuel":"Carburant","lbl_toll":"Péages",
    "lbl_vign":"Vignette CH","lbl_total":"TOTAL",
    "lbl_tip":"Conseil: fais le plein en","lbl_save":"économie",
    "lbl_traffic":"Trafic sur le trajet","lbl_parkings":"Parkings TIR sur le trajet",
    "lbl_weather":"Météo sur le trajet","lbl_no_traffic":"Trafic fluide — route dégagée",
    "lbl_no_tomtom":"(ajoute TOMTOM_KEY pour vérifier le trafic)",
    "fuel_prices":"*Prix diesel Europe*\n\nPas cher: Pologne 1.41€, Slovaquie 1.48€\nMoyens: France 1.65€, Allemagne 1.71€\nCher: Suisse 1.89€, Italie 1.95€",
    "rules_text":"*Règles UE 561/2006*\n\nJour max 9h · Semaine max 56h\nPause après 4.5h: 45 min\nRepos quotidien: 11h · Hebdo: 45h",
    "b_ask":"Choisis le pays:","pro_text":"*GidTrack Pro — 7€/mois*\n\nAbonnement: @gidtrack_support",
    "help_text":"*Commandes:*\n\n/route /parking /tacho /fuel /bans /emergency /currency /rules",
},
"en":{
    "welcome":"Hi! I'm *GidTrack Navigator* — your smart truck navigator and assistant!\n\nI calculate your route and instantly find:\n• Traffic jams and incidents en route\n• TIR parkings along the way\n• Weather at key points\n• Full trip cost\n\nChoose language:",
    "menu":"GidTrack Navigator Menu",
    "r_route":"Route + navigation","r_fuel":"Diesel prices",
    "r_parking":"TIR parkings","r_tacho":"Tachograph",
    "r_border":"Documents / Borders","r_bans":"Driving bans",
    "r_emergency":"Emergency numbers","r_currency":"Currency converter",
    "r_cmr":"Scan CMR","r_rules":"EU rules",
    "r_lang":"Language","r_pro":"Pro subscription","r_back":"Back",
    "ask_from":"Where are you departing?\n_Lyon, Berlin, Besancon, Milano_",
    "ask_to":"Where are you going?",
    "ask_w":"Total truck weight (GVW tonnes):",
    "w1":"7.5t","w2":"7.5—12t","w3":"12—20t","w4":"20—40t",
    "searching":"Calculating route...\nChecking traffic and finding TIR parkings along the way...",
    "not_found":"City not found. Check the name.",
    "ask_parking":"Type a city or send location — I'll find TIR parkings:",
    "search_parking":"Searching TIR parkings...","no_parking":"No TIR parkings found within 60 km.",
    "ask_emergency":"Choose country:","ask_bans":"Choose country for driving bans:",
    "ask_currency":"Amount and currency:\n_Example: 100 CHF or 500 PLN_",
    "tacho_menu":"Tachograph timer (EU Reg. 561/2006):",
    "tacho_start_btn":"Start driving","tacho_stop_btn":"Stop",
    "tacho_status_btn":"Status","tacho_reset_btn":"Reset (new week)",
    "tacho_started":"Timer started!\n\nEU Reg. 561/2006:\n• Max without break: *4.5h*\n• Mandatory break: *45 min*\n• Max per day: *9h*\n• Max per week: *56h*",
    "tacho_already":"Timer already running! Press Stop first.",
    "tacho_stopped":"Stop recorded.","tacho_not_started":"Timer not started.",
    "ask_cmr":"Send CMR photo. I'll read the delivery address.",
    "ocr_proc":"Reading...","ocr_nokey":"OCR unavailable. Add OCR_KEY to Railway.",
    "new_route":"New route","addr_found":"CMR address",
    "addr_none":"Address not found. Enter manually.","cmr_raw":"CMR text",
    "lbl_hgv":"HGV route (ORS-HGV)","lbl_std":"Standard route (OSRM)",
    "lbl_dist":"Distance","lbl_time":"Travel time",
    "lbl_weight":"Weight","lbl_cons":"Consumption",
    "lbl_fuel":"Fuel","lbl_toll":"Tolls",
    "lbl_vign":"CH Vignette","lbl_total":"TOTAL",
    "lbl_tip":"Tip: fill up in","lbl_save":"save",
    "lbl_traffic":"Traffic on route","lbl_parkings":"TIR parkings on route",
    "lbl_weather":"Weather on route","lbl_no_traffic":"No traffic — road clear",
    "lbl_no_tomtom":"(add TOMTOM_KEY to check traffic)",
    "fuel_prices":"*Diesel prices Europe*\n\nCheap: Poland 1.41€, Slovakia 1.48€\nAverage: France 1.65€, Germany 1.71€\nExpensive: Switzerland 1.89€, Italy 1.95€",
    "rules_text":"*EU Rules 561/2006*\n\nDay max 9h · Week max 56h\nBreak after 4.5h: 45 min\nDaily rest: 11h · Weekly: 45h",
    "b_ask":"Choose country:","pro_text":"*GidTrack Pro — €7/month*\n\nSubscribe: @gidtrack_support",
    "help_text":"*Commands:*\n\n/route /parking /tacho /fuel /bans /emergency /currency /rules",
},
"uk":{
    "welcome":"Привіт! Я *GidTrack Navigator* — розумний навігатор та помічник далекобійника!\n\nПрокладаю маршрут і знаходжу:\n• Пробки та інциденти на шляху\n• Стоянки TIR вздовж маршруту\n• Погоду в ключових точках\n• Повну вартість рейсу\n\nОбери мову:",
    "menu":"Головне меню GidTrack Navigator",
    "r_route":"Маршрут + навігація","r_fuel":"Ціни на дизель",
    "r_parking":"Стоянки TIR","r_tacho":"Тахограф",
    "r_border":"Документи / Кордони","r_bans":"Заборони руху",
    "r_emergency":"Екстрені номери","r_currency":"Конвертер валют",
    "r_cmr":"Скан CMR","r_rules":"Правила ЄС",
    "r_lang":"Мова","r_pro":"Pro підписка","r_back":"Назад",
    "ask_from":"Звідки їдеш?\n_Lyon, Berlin, Besancon, Milano_",
    "ask_to":"Куди їдеш?",
    "ask_w":"Повна вага вантажівки (брутто тонн):",
    "w1":"до 7.5т","w2":"7.5—12т","w3":"12—20т","w4":"20—40т",
    "searching":"Прокладаю маршрут...\nПеревіряю пробки і шукаю стоянки TIR...",
    "not_found":"Місто не знайдено. Перевір назву.",
    "ask_parking":"Напиши місто або відправ геолокацію — знайду стоянки TIR:",
    "search_parking":"Шукаю стоянки TIR...","no_parking":"Стоянок TIR не знайдено в 60 км.",
    "ask_emergency":"Обери країну:","ask_bans":"Обери країну для заборон:",
    "ask_currency":"Сума і валюта:\n_Приклад: 100 CHF або 500 PLN_",
    "tacho_menu":"Таймер тахографа (Рег. ЄС 561/2006):",
    "tacho_start_btn":"Старт водіння","tacho_stop_btn":"Зупинка",
    "tacho_status_btn":"Статус","tacho_reset_btn":"Скинути (новий тиждень)",
    "tacho_started":"Таймер запущено!\n\nЄС 561/2006:\n• Максимум без перерви: *4.5 год*\n• Обов'язкова перерва: *45 хв*\n• Максимум за день: *9 год*\n• Максимум за тиждень: *56 год*",
    "tacho_already":"Таймер вже запущено! Спочатку натисни Зупинка.",
    "tacho_stopped":"Зупинку зафіксовано.","tacho_not_started":"Таймер не запущено.",
    "ask_cmr":"Відправ фото CMR. Прочитаю адресу вивантаження.",
    "ocr_proc":"Читаю документ...","ocr_nokey":"OCR недоступний. Додай OCR_KEY у Railway.",
    "new_route":"Новий маршрут","addr_found":"Адреса з CMR",
    "addr_none":"Адресу не знайдено. Введи вручну.","cmr_raw":"Текст CMR",
    "lbl_hgv":"Вантажний маршрут (ORS-HGV)","lbl_std":"Стандартний маршрут (OSRM)",
    "lbl_dist":"Відстань","lbl_time":"Час у дорозі",
    "lbl_weight":"Вага","lbl_cons":"Витрата",
    "lbl_fuel":"Пальне","lbl_toll":"Платні дороги",
    "lbl_vign":"Víньєтка CH","lbl_total":"РАЗОМ",
    "lbl_tip":"Порада: заправся в","lbl_save":"економія",
    "lbl_traffic":"Пробки по маршруту","lbl_parkings":"Стоянки TIR по маршруту",
    "lbl_weather":"Погода по маршруту","lbl_no_traffic":"Пробок немає — дорога вільна",
    "lbl_no_tomtom":"(додай TOMTOM_KEY для перевірки пробок)",
    "fuel_prices":"*Ціни на дизель Європа*\n\nДешево: Польща 1.41€, Словаччина 1.48€\nСередні: Франція 1.65€, Австрія 1.68€\nДорого: Швейцарія 1.89€, Iталія 1.95€",
    "rules_text":"*Правила ЄС 561/2006*\n\nДень до 9г · Тиждень до 56г\nПісля 4.5г — 45хв перерва\nЩодобовий: 11г · Щотижневий: 45г",
    "b_ask":"Обери країну:","pro_text":"*GidTrack Pro — 7€/місяць*\n\nОформити: @gidtrack_support",
    "help_text":"*Команди:*\n\n/route /parking /tacho /fuel /bans /emergency /currency /rules",
},
}

# ─── API: ГЕОКОДИНГ ──────────────────────────────────────────────────────────
async def geocode(city: str):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q":city,"format":"json","limit":1,"addressdetails":1},
                headers={"User-Agent":"GidTrackNavigator/1.0 contact@gidtrack.eu"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                data = await r.json()
                if data:
                    d = data[0]
                    cc = d.get("address",{}).get("country_code","").upper()
                    return float(d["lon"]), float(d["lat"]), d["display_name"], cc
    except Exception as e:
        logger.error(f"geocode: {e}")
    return None, None, None, None

# ─── API: МАРШРУТ ORS (грузовой) ─────────────────────────────────────────────
async def get_route_ors(lon1, lat1, lon2, lat2, weight_t: float):
    if not ORS_KEY:
        return None, None, None
    try:
        payload = {
            "coordinates":[[lon1,lat1],[lon2,lat2]],
            "units":"km",
            "geometry":True,
            "options":{"profile_params":{"restrictions":{
                "weight":min(weight_t,40.0),
                "axleload":round(min(weight_t/4,12.0),1),
                "height":4.0,"width":2.55,"length":16.5,
            }}}
        }
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://api.openrouteservice.org/v2/directions/driving-hgv",
                json=payload,
                headers={"Authorization":ORS_KEY,"Content-Type":"application/json"},
                timeout=aiohttp.ClientTimeout(total=25)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    route = data["routes"][0]
                    seg = route["summary"]
                    km = round(seg["distance"])
                    h, m = divmod(round(seg["duration"]/60), 60)
                    dur = f"{h}h{m:02d}" if m else f"{h}h"
                    # Извлекаем промежуточные координаты из геометрии
                    waypoints = []
                    try:
                        coords = route["geometry"]["coordinates"]
                        step = max(1, len(coords)//5)
                        for i in range(0, len(coords), step):
                            waypoints.append((coords[i][1], coords[i][0]))
                    except Exception:
                        pass
                    return km, dur, waypoints
                logger.error(f"ORS {r.status}: {(await r.text())[:100]}")
    except Exception as e:
        logger.error(f"ORS: {e}")
    return None, None, None

# ─── API: МАРШРУТ OSRM (резервный) ───────────────────────────────────────────
async def get_route_osrm(lon1, lat1, lon2, lat2):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}",
                params={"overview":"false"},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                data = await r.json()
                if data.get("code") == "Ok":
                    rt = data["routes"][0]
                    km = round(rt["distance"]/1000)
                    h, m = divmod(round(rt["duration"]/60), 60)
                    dur = f"{h}h{m:02d}" if m else f"{h}h"
                    return km, dur
    except Exception as e:
        logger.error(f"OSRM: {e}")
    return None, None

# ─── API: TOMTOM TRAFFIC ──────────────────────────────────────────────────────
async def get_tomtom_traffic(lat: float, lon: float) -> dict:
    """
    TomTom Flow API — проверяет пробки в точке маршрута.
    Возвращает: скорость, задержку, описание.
    """
    if not TOMTOM_KEY:
        return {}
    try:
        url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
        async with aiohttp.ClientSession() as s:
            async with s.get(
                url,
                params={"key":TOMTOM_KEY,"point":f"{lat},{lon}","unit":"KMPH"},
                timeout=aiohttp.ClientTimeout(total=8)
            ) as r:
                if r.status == 200:
                    return await r.json()
    except Exception as e:
        logger.error(f"TomTom flow: {e}")
    return {}

async def get_tomtom_incidents(lat: float, lon: float, radius_m: int = 8000) -> list:
    """
    TomTom Incidents API — ДТП, ремонты, перекрытия в радиусе от точки маршрута.
    """
    if not TOMTOM_KEY:
        return []
    try:
        bbox = f"{lon-0.1},{lat-0.1},{lon+0.1},{lat+0.1}"
        url = "https://api.tomtom.com/traffic/services/5/incidentDetails"
        async with aiohttp.ClientSession() as s:
            async with s.get(
                url,
                params={"key":TOMTOM_KEY,"bbox":bbox,"fields":"{incidents{type,geometry,properties{iconCategory,magnitudeOfDelay,events{description,code},startTime,endTime,from,to,length,delay}}}","language":"ru-RU","t":"-1","timeValidityFilter":"present"},
                timeout=aiohttp.ClientTimeout(total=8)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get("incidents", [])
    except Exception as e:
        logger.error(f"TomTom incidents: {e}")
    return []

def parse_tomtom_flow(data: dict, lang: str) -> str:
    """Разбирает ответ TomTom Flow и возвращает читаемый текст"""
    try:
        fd = data.get("flowSegmentData", {})
        current_speed = fd.get("currentSpeed", 0)
        free_flow = fd.get("freeFlowSpeed", current_speed)
        if free_flow == 0:
            return ""
        ratio = current_speed / free_flow
        delay_min = round((free_flow - current_speed) / max(free_flow, 1) * 60)

        if ratio >= 0.85:
            return ""  # дорога свободна — не показываем
        elif ratio >= 0.6:
            level = "умеренные пробки" if lang=="ru" else "trafic modéré" if lang=="fr" else "moderate traffic" if lang=="en" else "помірні пробки"
        elif ratio >= 0.4:
            level = "сильные пробки" if lang=="ru" else "trafic dense" if lang=="fr" else "heavy traffic" if lang=="en" else "сильні пробки"
        else:
            level = "ПРОБКА — стоим" if lang=="ru" else "EMBOUTEILLAGE" if lang=="fr" else "TRAFFIC JAM" if lang=="en" else "ПРОБКА — стоїмо"

        speed_txt = f"{current_speed} км/ч" if lang in ("ru","uk") else f"{current_speed} km/h"
        delay_txt = f"+{delay_min} мин" if lang in ("ru","uk") else f"+{delay_min} min"
        return f"{level} ({speed_txt}, задержка {delay_txt})" if lang in ("ru","uk") else f"{level} ({speed_txt}, delay {delay_txt})"
    except Exception:
        return ""

def parse_tomtom_incidents(incidents: list, lang: str) -> list:
    """Разбирает инциденты TomTom и возвращает список важных событий"""
    results = []
    type_names_ru = {
        "ACCIDENT": "ДТП", "FOG": "Туман", "DANGEROUS_CONDITIONS": "Опасные условия",
        "RAIN": "Дождь", "ICE": "Лёд", "JAM": "Пробка", "LANE_CLOSED": "Полоса закрыта",
        "ROAD_CLOSED": "Дорога закрыта", "ROAD_WORKS": "Ремонт дороги", "WIND": "Сильный ветер",
        "FLOODING": "Наводнение", "DETOUR": "Объезд",
    }
    type_names_fr = {
        "ACCIDENT":"Accident","FOG":"Brouillard","DANGEROUS_CONDITIONS":"Conditions dangereuses",
        "RAIN":"Pluie","ICE":"Verglas","JAM":"Embouteillage","LANE_CLOSED":"Voie fermée",
        "ROAD_CLOSED":"Route fermée","ROAD_WORKS":"Travaux","WIND":"Vent fort","DETOUR":"Déviation",
    }
    type_names_en = {
        "ACCIDENT":"Accident","FOG":"Fog","DANGEROUS_CONDITIONS":"Dangerous conditions",
        "RAIN":"Rain","ICE":"Ice","JAM":"Traffic jam","LANE_CLOSED":"Lane closed",
        "ROAD_CLOSED":"Road closed","ROAD_WORKS":"Roadworks","WIND":"Strong wind","DETOUR":"Detour",
    }
    names = type_names_ru if lang in ("ru","uk") else type_names_fr if lang=="fr" else type_names_en

    for inc in incidents[:4]:
        props = inc.get("properties", {})
        itype = props.get("iconCategory","").upper()
        delay = props.get("magnitudeOfDelay", 0)
        if delay < 1:
            continue
        name = names.get(itype, itype)
        from_road = props.get("from","")
        to_road = props.get("to","")
        events = props.get("events",[])
        desc = events[0].get("description","") if events else ""

        delay_labels = {0:"незначительная",1:"умеренная",2:"значительная",3:"большая",4:"очень большая"}
        delay_fr = {0:"mineure",1:"modérée",2:"importante",3:"majeure",4:"très majeure"}
        delay_en = {0:"minor",1:"moderate",2:"major",3:"serious",4:"very serious"}
        dlbl = (delay_labels if lang in ("ru","uk") else delay_fr if lang=="fr" else delay_en).get(delay,"")

        road_info = f"{from_road}→{to_road}" if from_road and to_road else desc[:40] if desc else ""
        results.append(f"{name}{' — '+dlbl if dlbl else ''}{': '+road_info if road_info else ''}")
    return results

# ─── API: СТОЯНКИ TIR (Overpass) ─────────────────────────────────────────────
async def find_tir_parkings_near(lat: float, lon: float, radius_km: int = 50) -> list:
    """Ищет стоянки TIR через Overpass API рядом с точкой маршрута"""
    try:
        r_m = radius_km * 1000
        query = f"""
[out:json][timeout:20];
(
  node["amenity"="truck_stop"](around:{r_m},{lat},{lon});
  node["amenity"="parking"]["hgv"="yes"](around:{r_m},{lat},{lon});
  node["amenity"="parking"]["hgv"="designated"](around:{r_m},{lat},{lon});
  node["amenity"="parking"]["access"="yes"]["hgv"~"yes|designated"](around:{r_m},{lat},{lon});
  way["amenity"="truck_stop"](around:{r_m},{lat},{lon});
  way["amenity"="parking"]["hgv"="yes"](around:{r_m},{lat},{lon});
);
out center 5;
"""
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://overpass-api.de/api/interpreter",
                data=query,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as r:
                data = await r.json()
                return data.get("elements", [])
    except Exception as e:
        logger.error(f"Overpass: {e}")
    return []

def format_parking_short(p: dict, ref_lat: float, ref_lon: float) -> str:
    """Краткое описание стоянки для вставки в результат маршрута"""
    tags = p.get("tags", {})
    clat = p.get("lat") or p.get("center",{}).get("lat", ref_lat)
    clon = p.get("lon") or p.get("center",{}).get("lon", ref_lon)
    name = tags.get("name") or tags.get("operator") or "TIR Parking"
    dist = round(haversine(ref_lat, ref_lon, clat, clon))

    amenities = []
    if tags.get("shower") in ("yes","fee"): amenities.append("душ")
    if tags.get("toilets") or tags.get("toilets:disposal"): amenities.append("WC")
    if tags.get("restaurant")=="yes" or tags.get("food")=="yes": amenities.append("кафе")
    if tags.get("security") in ("yes","guard","camera"): amenities.append("охрана")
    if tags.get("wifi")=="yes": amenities.append("WiFi")
    fee = " (плат.)" if tags.get("fee") not in (None,"","no") else " (беспл.)" if tags.get("fee")=="no" else ""

    am = " · ".join(amenities) if amenities else ""
    maps_url = f"https://maps.google.com/?q={clat},{clon}"
    line = f"*{name}*{fee} ~{dist} км"
    if am:
        line += f"\n_{am}_"
    line += f"\n{maps_url}"
    return line

# ─── API: ПОГОДА (Open-Meteo) ─────────────────────────────────────────────────
async def get_weather_point(lat: float, lon: float) -> dict:
    """Погода в точке через Open-Meteo — без ключа"""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude":lat,"longitude":lon,
                    "current":"temperature_2m,wind_speed_10m,weather_code,visibility,precipitation",
                    "timezone":"auto","forecast_days":1,
                },
                timeout=aiohttp.ClientTimeout(total=8)
            ) as r:
                return await r.json()
    except Exception as e:
        logger.error(f"Weather: {e}")
    return {}

def check_weather_alert(data: dict, lang: str) -> str:
    """Проверяет опасные условия погоды и возвращает предупреждение"""
    if not data:
        return ""
    cur = data.get("current", {})
    temp = cur.get("temperature_2m", 10)
    wind = cur.get("wind_speed_10m", 0)
    wcode = cur.get("weather_code", 0)
    vis = cur.get("visibility", 10000)
    precip = cur.get("precipitation", 0)

    alerts = []

    # Туман
    if wcode in (45, 48) or (vis is not None and vis < 200):
        if lang == "ru": alerts.append("ТУМАН — видимость менее 200 м!")
        elif lang == "fr": alerts.append("BROUILLARD — visibilité < 200 m!")
        elif lang == "en": alerts.append("FOG — visibility < 200 m!")
        else: alerts.append("ТУМАН — видимість менше 200 м!")

    # Гололёд / снег
    if temp <= 2 and wcode in list(range(51,68)) + list(range(71,78)):
        if lang == "ru": alerts.append(f"ГОЛОЛЁД — t°{temp}°C + осадки!")
        elif lang == "fr": alerts.append(f"VERGLAS — t°{temp}°C + précip!")
        elif lang == "en": alerts.append(f"ICE — t°{temp}°C + precipitation!")
        else: alerts.append(f"ОЖЕЛЕДИЦЯ — t°{temp}°C + опади!")

    # Сильный ветер для фуры (опасен при > 60 км/ч)
    if wind >= 60:
        w_round = round(wind)
        if lang == "ru": alerts.append(f"СИЛЬНЫЙ ВЕТЕР — {w_round} км/ч (опасно для фуры!)")
        elif lang == "fr": alerts.append(f"VENT FORT — {w_round} km/h (dangereux PL!)")
        elif lang == "en": alerts.append(f"STRONG WIND — {w_round} km/h (dangerous for trucks!)")
        else: alerts.append(f"СИЛЬНИЙ ВІТЕР — {w_round} км/год (небезпечно для фури!)")

    # Гроза
    if wcode in range(95, 100):
        if lang == "ru": alerts.append("ГРОЗА — снизь скорость!")
        elif lang == "fr": alerts.append("ORAGE — réduire la vitesse!")
        elif lang == "en": alerts.append("THUNDERSTORM — reduce speed!")
        else: alerts.append("ГРОЗА — знизь швидкість!")

    # Снегопад
    if wcode in (73, 75, 85, 86):
        if lang == "ru": alerts.append("СИЛЬНЫЙ СНЕГ — возможно закрытие дорог!")
        elif lang == "fr": alerts.append("FORTE NEIGE — routes pourraient fermer!")
        elif lang == "en": alerts.append("HEAVY SNOW — roads may close!")
        else: alerts.append("СИЛЬНИЙ СНІГОПАД — можливо закриття доріг!")

    return "\n".join(alerts)

def get_weather_desc(wcode: int, temp: float, lang: str) -> str:
    codes = WEATHER_CODES_FR if lang=="fr" else WEATHER_CODES_EN if lang=="en" else WEATHER_CODES
    desc = codes.get(wcode, str(wcode))
    return f"{desc}, {temp}°C"

# ─── OCR ─────────────────────────────────────────────────────────────────────
async def do_ocr(photo_bytes: bytes):
    if not OCR_KEY:
        return None
    try:
        b64 = base64.b64encode(photo_bytes).decode()
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://api.ocr.space/parse/image",
                data={"base64Image":f"data:image/jpeg;base64,{b64}",
                      "apikey":OCR_KEY,"language":"eng",
                      "isOverlayRequired":False,"detectOrientation":True},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as r:
                res = await r.json()
                if res.get("IsErroredOnProcessing"): return None
                pr = res.get("ParsedResults",[])
                return pr[0].get("ParsedText","") if pr else None
    except Exception as e:
        logger.error(f"OCR: {e}")
    return None

def extract_address(text: str):
    kw = ["street","rue","str.","strasse","via","viale","allee","avenue",
          "blvd","boulevard","road","rd","lane","place","piazza","platz",
          "ul.","ул.","вул.","alej","gasse","laan","weg","chaussee"]
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines:
        if any(k in line.lower() for k in kw) and 8 < len(line) < 120:
            return line
    for line in lines:
        if re.search(r'\b\d{4,5}\b', line) and 8 < len(line) < 120:
            return line
    return None

# ─── ВАЛЮТЫ ──────────────────────────────────────────────────────────────────
def parse_currency(text: str):
    m = re.search(r'(\d+[\.,]?\d*)\s*([A-Z]{3})', text.upper())
    if not m:
        m = re.search(r'([A-Z]{3})\s*(\d+[\.,]?\d*)', text.upper())
        if m: return float(m.group(2).replace(",",".")), m.group(1)
        return None, None
    return float(m.group(1).replace(",",".")), m.group(2)

def convert_currency(amount: float, from_curr: str, lang: str) -> str:
    if from_curr == "EUR":
        lines = []
        for curr, rate in sorted(RATES_EUR.items()):
            lines.append(f"{curr}: *{round(amount * rate)}*")
        return "\n".join(lines)
    rate = RATES_EUR.get(from_curr)
    if not rate:
        return "Валюта не найдена" if lang=="ru" else "Devise inconnue" if lang=="fr" else "Currency not found"
    eur = round(amount / rate, 2)
    lines = [f"{amount} {from_curr} = *{eur} EUR*", ""]
    for curr, r in sorted(RATES_EUR.items()):
        if curr != from_curr:
            lines.append(f"{curr}: *{round(eur * r)}*")
    return "\n".join(lines[:12])

# ─── ТАХОГРАФ ─────────────────────────────────────────────────────────────────
def tacho_status_text(u: dict, lang: str) -> str:
    start = u.get("tacho_start")
    if not start:
        msg = {"ru":"Таймер не запущен","fr":"Minuteur non démarré","en":"Timer not started","uk":"Таймер не запущено"}
        return msg.get(lang, msg["ru"])
    elapsed = (datetime.now() - start).total_seconds() / 3600
    remaining = max(0, 4.5 - elapsed)
    daily = u.get("tacho_daily", 0) + elapsed
    weekly = u.get("tacho_weekly", 0) + daily

    need_break = remaining <= 0
    warn_break = 0 < remaining <= 0.25  # менее 15 мин

    if lang == "ru":
        status = "ТРЕБУЕТСЯ ПЕРЕРЫВ 45 МИН!" if need_break else (f"Осталось до перерыва: *{remaining:.1f} ч* ⚠️" if warn_break else f"До перерыва: *{remaining:.1f} ч*")
        return (f"*Тахограф — статус*\n\n"
                f"Едешь сейчас: *{elapsed:.1f} ч*\n"
                f"День итого: *{daily:.1f} / 9 ч*\n"
                f"Неделя итого: *{weekly:.1f} / 56 ч*\n\n"
                f"{status}")
    elif lang == "fr":
        status = "PAUSE OBLIGATOIRE 45 MIN!" if need_break else (f"Avant pause: *{remaining:.1f}h* ⚠️" if warn_break else f"Avant pause: *{remaining:.1f}h*")
        return (f"*Tachygraphe — statut*\n\n"
                f"En conduite: *{elapsed:.1f}h*\n"
                f"Journée: *{daily:.1f} / 9h*\n"
                f"Semaine: *{weekly:.1f} / 56h*\n\n"
                f"{status}")
    elif lang == "uk":
        status = "ПОТРІБНА ПЕРЕРВА 45 ХВ!" if need_break else (f"До перерви: *{remaining:.1f} год* ⚠️" if warn_break else f"До перерви: *{remaining:.1f} год*")
        return (f"*Тахограф — статус*\n\n"
                f"Їдеш зараз: *{elapsed:.1f} год*\n"
                f"День всього: *{daily:.1f} / 9 год*\n"
                f"Тиждень: *{weekly:.1f} / 56 год*\n\n"
                f"{status}")
    else:
        status = "MANDATORY BREAK 45 MIN!" if need_break else (f"Before break: *{remaining:.1f}h* ⚠️" if warn_break else f"Before break: *{remaining:.1f}h*")
        return (f"*Tachograph — status*\n\n"
                f"Driving: *{elapsed:.1f}h*\n"
                f"Day total: *{daily:.1f} / 9h*\n"
                f"Week total: *{weekly:.1f} / 56h*\n\n"
                f"{status}")

# ─── РАСЧЁТ СТОИМОСТИ ────────────────────────────────────────────────────────
def build_cost(km: int, cc1: str, cc2: str, weight: float, lang: str, rtype: str = "STD") -> tuple:
    t = T[lang]
    cons = get_cons(weight)
    fp = round((DIESEL.get(cc1,1.65) + DIESEL.get(cc2,1.65)) / 2, 2)
    fl = round(km * cons / 100)
    fc = round(fl * fp)

    if cc1 == "CH" or cc2 == "CH":
        toll, tlbl = CH_VIGNETTE, t["lbl_vign"]
    else:
        toll = round(km * max(TOLL.get(cc1,10), TOLL.get(cc2,10)) / 100)
        tlbl = t["lbl_toll"]
    total = fc + toll

    cheapest = min(DIESEL, key=DIESEL.get)
    saving = round(fl * (fp - DIESEL[cheapest]))
    cnames_map = {
        "ru":{"BG":"Болгария","UA":"Украина","RO":"Румыния","PL":"Польша","SK":"Словакия","LU":"Люксембург"},
        "uk":{"BG":"Болгарія","UA":"Україна","RO":"Румунія","PL":"Польща","SK":"Словаччина","LU":"Люксембург"},
        "fr":{"BG":"Bulgarie","UA":"Ukraine","RO":"Roumanie","PL":"Pologne","SK":"Slovaquie","LU":"Luxembourg"},
        "en":{"BG":"Bulgaria","UA":"Ukraine","RO":"Romania","PL":"Poland","SK":"Slovakia","LU":"Luxembourg"},
    }
    cname = cnames_map.get(lang, cnames_map["en"]).get(cheapest, cheapest)
    rlbl = t["lbl_hgv"] if rtype == "HGV" else t["lbl_std"]
    unit = "km" if lang in ("fr","en") else "км"

    lines = [
        f"*{rlbl}*",
        f"{t['lbl_dist']}: *{km} {unit}* | {t['lbl_time']}: *{{DUR}}*",
        f"{t['lbl_weight']}: *{weight}t* | {t['lbl_cons']}: *{cons}l/100{unit}*",
        "",
        f"{t['lbl_fuel']}: {fl}l × {fp}€ = *{fc}€*",
        f"{tlbl}: *{toll}€*",
        "",
        f"*{t['lbl_total']}: {total}€*",
    ]
    if saving > 10:
        lines.append(f"\n{t['lbl_tip']} {cname} — {t['lbl_save']} ~{saving}€")
    return "\n".join(lines), total

# ─── ГЛАВНАЯ ФУНКЦИЯ МАРШРУТА (всё в одном) ──────────────────────────────────
async def build_full_route_message(city_from: str, city_to: str, weight: float, lang: str) -> str:
    """
    Симбиоз навигатора и помощника:
    1. Прокладывает грузовой маршрут ORS/OSRM
    2. Проверяет пробки TomTom по точкам маршрута
    3. Находит стоянки TIR вдоль маршрута
    4. Проверяет погоду по контрольным точкам
    5. Считает полную стоимость рейса
    """
    t = T[lang]

    # 1. Геокодинг
    lon1, lat1, _, cc1 = await geocode(city_from)
    lon2, lat2, _, cc2 = await geocode(city_to)
    if not (lon1 and lon2):
        return t["not_found"]

    # 2. Маршрут
    waypoints = []
    rtype = "STD"
    km, dur = None, None

    if ORS_KEY:
        km, dur, waypoints = await get_route_ors(lon1, lat1, lon2, lat2, weight)
        if km:
            rtype = "HGV"

    if not km:
        km, dur = await get_route_osrm(lon1, lat1, lon2, lat2)
        if not km:
            return t["not_found"]
        # Генерируем промежуточные точки для OSRM
        waypoints = [(lat1, lon1)] + interpolate_points(lat1, lon1, lat2, lon2, step_km=200) + [(lat2, lon2)]

    if not waypoints:
        waypoints = interpolate_points(lat1, lon1, lat2, lon2, step_km=200)

    # 3. Параллельный запрос: пробки + стоянки + погода
    # Выбираем контрольные точки: начало, середина маршрута, конец
    check_points = []
    if waypoints:
        mid_idx = len(waypoints) // 2
        check_points = list({0: waypoints[0], mid_idx: waypoints[mid_idx], -1: waypoints[-1]}.values())
    else:
        check_points = [(lat1, lon1), (lat2, lon2)]

    # Запросы пробок и погоды по контрольным точкам
    traffic_alerts = []
    weather_alerts = []
    parking_results = []

    import asyncio

    async def fetch_point_data(pt_lat, pt_lon, is_parking_point):
        flow_data = await get_tomtom_traffic(pt_lat, pt_lon)
        incidents = await get_tomtom_incidents(pt_lat, pt_lon)
        weather_data = await get_weather_point(pt_lat, pt_lon)
        parkings = []
        if is_parking_point:
            parkings = await find_tir_parkings_near(pt_lat, pt_lon, radius_km=40)
        return flow_data, incidents, weather_data, parkings

    # Точки для поиска стоянок: каждые ~300 км
    parking_interval = max(1, km // 300) if km else 1
    tasks = []
    for i, (pt_lat, pt_lon) in enumerate(check_points):
        is_parking = (i % parking_interval == 0) or (i == len(check_points)-1)
        tasks.append(fetch_point_data(pt_lat, pt_lon, is_parking))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    seen_parkings = set()
    for res in results:
        if isinstance(res, Exception):
            continue
        flow_data, incidents, weather_data, parkings = res

        # Пробки
        flow_txt = parse_tomtom_flow(flow_data, lang)
        if flow_txt:
            traffic_alerts.append(flow_txt)
        incident_list = parse_tomtom_incidents(incidents, lang)
        traffic_alerts.extend(incident_list)

        # Погода
        w_alert = check_weather_alert(weather_data, lang)
        if w_alert:
            for line in w_alert.split("\n"):
                if line and line not in weather_alerts:
                    weather_alerts.append(line)

        # Стоянки (дедупликация)
        for p in parkings:
            p_lat = p.get("lat") or p.get("center",{}).get("lat")
            p_lon = p.get("lon") or p.get("center",{}).get("lon")
            if not p_lat:
                continue
            key = (round(p_lat,3), round(p_lon,3))
            if key not in seen_parkings:
                seen_parkings.add(key)
                parking_results.append(p)

    # 4. Стоимость
    cost_text, total = build_cost(km, cc1 or "FR", cc2 or "FR", weight, lang, rtype)
    cost_text = cost_text.replace("{DUR}", str(dur))

    # 5. Собираем финальное сообщение
    cname_from = city_from.title()
    cname_to   = city_to.title()

    lines = [f"*{cname_from} — {cname_to}*\n"]

    # Стоимость маршрута
    lines.append(cost_text)

    # Пробки
    lines.append(f"\n*{t['lbl_traffic']}:*")
    if traffic_alerts:
        # Убираем дубликаты
        seen = set()
        for a in traffic_alerts:
            if a not in seen:
                seen.add(a)
                lines.append(f"• {a}")
    elif TOMTOM_KEY:
        lines.append(f"• {t['lbl_no_traffic']}")
    else:
        lines.append(f"• {t['lbl_no_tomtom']}")

    # Погода
    if weather_alerts:
        lines.append(f"\n*{t['lbl_weather']}:*")
        for wa in weather_alerts[:3]:
            lines.append(f"• {wa}")

    # Стоянки TIR по маршруту
    lines.append(f"\n*{t['lbl_parkings']}:*")
    if parking_results:
        for p in parking_results[:4]:
            p_lat = p.get("lat") or p.get("center",{}).get("lat", lat2)
            p_lon = p.get("lon") or p.get("center",{}).get("lon", lon2)
            lines.append(format_parking_short(p, p_lat, p_lon))
            lines.append("")
    else:
        no_p = {"ru":"Охраняемых стоянок TIR не найдено. Проверь на truck24.eu","fr":"Aucun parking TIR trouvé. Vérifier sur truck24.eu","en":"No TIR parkings found. Check truck24.eu","uk":"Стоянок TIR не знайдено. Перевір на truck24.eu"}
        lines.append(no_p.get(lang, no_p["ru"]))

    return "\n".join(lines)

# ─── КЛАВИАТУРЫ ──────────────────────────────────────────────────────────────
def kb_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Українська", callback_data="lang_uk"),
         InlineKeyboardButton("Русский",    callback_data="lang_ru")],
        [InlineKeyboardButton("Français",   callback_data="lang_fr"),
         InlineKeyboardButton("English",    callback_data="lang_en")],
    ])

def kb_menu(uid: int):
    t = T[ud(uid)["lang"]]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["r_route"],     callback_data="m_route")],
        [InlineKeyboardButton(t["r_fuel"],      callback_data="m_fuel"),
         InlineKeyboardButton(t["r_rules"],     callback_data="m_rules")],
        [InlineKeyboardButton(t["r_parking"],   callback_data="m_parking"),
         InlineKeyboardButton(t["r_tacho"],     callback_data="m_tacho")],
        [InlineKeyboardButton(t["r_border"],    callback_data="m_border"),
         InlineKeyboardButton(t["r_bans"],      callback_data="m_bans")],
        [InlineKeyboardButton(t["r_emergency"], callback_data="m_emergency"),
         InlineKeyboardButton(t["r_currency"],  callback_data="m_currency")],
        [InlineKeyboardButton(t["r_cmr"],       callback_data="m_cmr"),
         InlineKeyboardButton(t["r_pro"],       callback_data="m_pro")],
        [InlineKeyboardButton(t["r_lang"],      callback_data="m_lang")],
    ])

def kb_back(uid: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(T[ud(uid)["lang"]]["r_back"], callback_data="back")
    ]])

def kb_weight(uid: int):
    t = T[ud(uid)["lang"]]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["w1"], callback_data="w_7.5"),
         InlineKeyboardButton(t["w2"], callback_data="w_12")],
        [InlineKeyboardButton(t["w3"], callback_data="w_20"),
         InlineKeyboardButton(t["w4"], callback_data="w_40")],
        [InlineKeyboardButton(t["r_back"], callback_data="back")],
    ])

def kb_border(uid: int):
    t = T[ud(uid)["lang"]]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Швейцария / Suisse",   callback_data="b_CH")],
        [InlineKeyboardButton("Германия / Allemagne", callback_data="b_DE")],
        [InlineKeyboardButton("Италия / Italie",      callback_data="b_IT")],
        [InlineKeyboardButton("Франция / France",     callback_data="b_FR")],
        [InlineKeyboardButton("Австрия / Autriche",   callback_data="b_AT")],
        [InlineKeyboardButton("Польша / Pologne",     callback_data="b_PL")],
        [InlineKeyboardButton(t["r_back"],             callback_data="back")],
    ])

def kb_bans(uid: int):
    t = T[ud(uid)["lang"]]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Франция / France", callback_data="ban_FR"),
         InlineKeyboardButton("Германия / DE",    callback_data="ban_DE")],
        [InlineKeyboardButton("Италия / Italy",   callback_data="ban_IT"),
         InlineKeyboardButton("Швейцария / CH",   callback_data="ban_CH")],
        [InlineKeyboardButton("Австрия / AT",     callback_data="ban_AT"),
         InlineKeyboardButton("Польша / PL",      callback_data="ban_PL")],
        [InlineKeyboardButton("Бельгия / BE",     callback_data="ban_BE"),
         InlineKeyboardButton("Испания / ES",     callback_data="ban_ES")],
        [InlineKeyboardButton(t["r_back"],         callback_data="back")],
    ])

def kb_emergency(uid: int):
    t = T[ud(uid)["lang"]]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Франция",    callback_data="em_FR"),
         InlineKeyboardButton("Германия",   callback_data="em_DE"),
         InlineKeyboardButton("Италия",     callback_data="em_IT")],
        [InlineKeyboardButton("Швейцария",  callback_data="em_CH"),
         InlineKeyboardButton("Австрия",    callback_data="em_AT"),
         InlineKeyboardButton("Польша",     callback_data="em_PL")],
        [InlineKeyboardButton("Бельгия",    callback_data="em_BE"),
         InlineKeyboardButton("Нидерланды", callback_data="em_NL"),
         InlineKeyboardButton("Испания",    callback_data="em_ES")],
        [InlineKeyboardButton("Чехия",      callback_data="em_CZ"),
         InlineKeyboardButton("Венгрия",    callback_data="em_HU"),
         InlineKeyboardButton("Румыния",    callback_data="em_RO")],
        [InlineKeyboardButton(t["r_back"],   callback_data="back")],
    ])

def kb_tacho(uid: int):
    t = T[ud(uid)["lang"]]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["tacho_start_btn"],  callback_data="tacho_start"),
         InlineKeyboardButton(t["tacho_stop_btn"],   callback_data="tacho_stop")],
        [InlineKeyboardButton(t["tacho_status_btn"], callback_data="tacho_status"),
         InlineKeyboardButton(t["tacho_reset_btn"],  callback_data="tacho_reset")],
        [InlineKeyboardButton(t["r_back"],            callback_data="back")],
    ])

def kb_after_route(uid: int):
    t = T[ud(uid)["lang"]]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["new_route"],   callback_data="m_route")],
        [InlineKeyboardButton(t["r_border"],    callback_data="m_border"),
         InlineKeyboardButton(t["r_tacho"],     callback_data="m_tacho")],
        [InlineKeyboardButton(t["r_bans"],      callback_data="m_bans"),
         InlineKeyboardButton(t["r_emergency"], callback_data="m_emergency")],
        [InlineKeyboardButton(t["r_back"],      callback_data="back")],
    ])

# ─── ХЭНДЛЕРЫ ────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud(uid)["step"] = ""
    await update.message.reply_text(
        T["ru"]["welcome"], reply_markup=kb_lang(), parse_mode="Markdown")

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        T[ud(uid)["lang"]]["help_text"], reply_markup=kb_back(uid), parse_mode="Markdown")

async def cmd_fuel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        T[ud(uid)["lang"]]["fuel_prices"], reply_markup=kb_back(uid), parse_mode="Markdown")

async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        T[ud(uid)["lang"]]["rules_text"], reply_markup=kb_back(uid), parse_mode="Markdown")

async def cmd_route(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud(uid)["step"] = "from"
    await update.message.reply_text(
        T[ud(uid)["lang"]]["ask_from"], reply_markup=kb_back(uid), parse_mode="Markdown")

async def cmd_parking(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud(uid)["step"] = "parking"
    await update.message.reply_text(
        T[ud(uid)["lang"]]["ask_parking"], reply_markup=kb_back(uid), parse_mode="Markdown")

async def cmd_tacho(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        T[ud(uid)["lang"]]["tacho_menu"], reply_markup=kb_tacho(uid), parse_mode="Markdown")

async def cmd_bans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        T[ud(uid)["lang"]]["ask_bans"], reply_markup=kb_bans(uid), parse_mode="Markdown")

async def cmd_emergency(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        T[ud(uid)["lang"]]["ask_emergency"], reply_markup=kb_emergency(uid), parse_mode="Markdown")

async def cmd_currency(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud(uid)["step"] = "currency"
    await update.message.reply_text(
        T[ud(uid)["lang"]]["ask_currency"], reply_markup=kb_back(uid), parse_mode="Markdown")

async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = ud(uid); l = u["lang"]; t = T[l]
    d = q.data

    if d.startswith("lang_"):
        u["lang"] = d[5:]; l = u["lang"]; t = T[l]; u["step"] = ""
        await q.edit_message_text(t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")

    elif d in ("back", "m_lang"):
        u["step"] = ""
        if d == "m_lang":
            await q.edit_message_text(t["welcome"], reply_markup=kb_lang(), parse_mode="Markdown")
        else:
            await q.edit_message_text(t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")

    elif d == "m_fuel":
        await q.edit_message_text(t["fuel_prices"], reply_markup=kb_back(uid), parse_mode="Markdown")
    elif d == "m_rules":
        await q.edit_message_text(t["rules_text"], reply_markup=kb_back(uid), parse_mode="Markdown")
    elif d == "m_pro":
        await q.edit_message_text(t["pro_text"], reply_markup=kb_back(uid), parse_mode="Markdown")
    elif d == "m_border":
        await q.edit_message_text(t["b_ask"], reply_markup=kb_border(uid), parse_mode="Markdown")
    elif d == "m_bans":
        await q.edit_message_text(t["ask_bans"], reply_markup=kb_bans(uid), parse_mode="Markdown")
    elif d == "m_emergency":
        await q.edit_message_text(t["ask_emergency"], reply_markup=kb_emergency(uid), parse_mode="Markdown")
    elif d == "m_currency":
        u["step"] = "currency"
        await q.edit_message_text(t["ask_currency"], reply_markup=kb_back(uid), parse_mode="Markdown")
    elif d == "m_parking":
        u["step"] = "parking"
        await q.edit_message_text(t["ask_parking"], reply_markup=kb_back(uid), parse_mode="Markdown")
    elif d == "m_tacho":
        await q.edit_message_text(t["tacho_menu"], reply_markup=kb_tacho(uid), parse_mode="Markdown")
    elif d == "m_cmr":
        if not OCR_KEY:
            await q.edit_message_text(t["ocr_nokey"], reply_markup=kb_back(uid), parse_mode="Markdown")
        else:
            u["step"] = "cmr"
            await q.edit_message_text(t["ask_cmr"], reply_markup=kb_back(uid), parse_mode="Markdown")
    elif d == "m_route":
        u["step"] = "from"
        await q.edit_message_text(t["ask_from"], reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d.startswith("b_"):
        cc = d[2:]
        doc = BORDER.get(cc,{}).get(l) or BORDER.get(cc,{}).get("ru","Not found")
        await q.edit_message_text(doc, reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d.startswith("ban_"):
        cc = d[4:]
        bans_list = BANS.get(cc, ["Нет данных"])
        bans_text = "\n".join(f"• {b}" for b in bans_list)
        names = {"FR":"Франция","DE":"Германия","IT":"Италия","CH":"Швейцария","AT":"Австрия","PL":"Польша","BE":"Бельгия","ES":"Испания"}
        await q.edit_message_text(
            f"*{names.get(cc,cc)} — запреты движения*\n\n{bans_text}",
            reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d.startswith("em_"):
        cc = d[3:]
        em = EMERGENCY.get(cc, {})
        if em:
            info = em.get("info","")
            txt = (f"*Экстренные номера — {cc}*\n\n"
                   f"Полиция: *{em['police']}*\n"
                   f"Скорая: *{em['ambulance']}*\n"
                   f"Пожарные: *{em['fire']}*\n"
                   f"ЕС единый: *{em['eu']}*\n"
                   f"Помощь на дороге: *{em['road']}*\n"
                   f"\n_{info}_")
            await q.edit_message_text(txt, reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d.startswith("tacho_"):
        action = d[6:]
        if action == "start":
            if u.get("tacho_start"):
                await q.edit_message_text(t["tacho_already"], reply_markup=kb_tacho(uid), parse_mode="Markdown")
            else:
                u["tacho_start"] = datetime.now()
                await q.edit_message_text(t["tacho_started"], reply_markup=kb_tacho(uid), parse_mode="Markdown")
        elif action == "stop":
            if u.get("tacho_start"):
                elapsed = (datetime.now() - u["tacho_start"]).total_seconds() / 3600
                u["tacho_daily"] = u.get("tacho_daily",0) + elapsed
                u["tacho_weekly"] = u.get("tacho_weekly",0) + elapsed
                u["tacho_start"] = None
                h_e, m_e = divmod(int(elapsed*60), 60)
                dur_str = f"{h_e}h{m_e:02d}m"
                lbl = {"ru":f"*Остановка*\nЗа сессию: *{dur_str}*\nДень итого: *{u['tacho_daily']:.1f} ч*",
                       "fr":f"*Arrêt*\nSession: *{dur_str}*\nJournée: *{u['tacho_daily']:.1f}h*",
                       "en":f"*Stop*\nSession: *{dur_str}*\nDay total: *{u['tacho_daily']:.1f}h*",
                       "uk":f"*Зупинка*\nЗа сесію: *{dur_str}*\nДень всього: *{u['tacho_daily']:.1f} год*"}
                await q.edit_message_text(lbl.get(l,lbl["ru"]), reply_markup=kb_tacho(uid), parse_mode="Markdown")
            else:
                await q.edit_message_text(t["tacho_not_started"], reply_markup=kb_tacho(uid), parse_mode="Markdown")
        elif action == "status":
            await q.edit_message_text(tacho_status_text(u, l), reply_markup=kb_tacho(uid), parse_mode="Markdown")
        elif action == "reset":
            u["tacho_start"] = None; u["tacho_daily"] = 0.0; u["tacho_weekly"] = 0.0
            lbl = {"ru":"Тахограф сброшен.","fr":"Tachygraphe réinitialisé.","en":"Tachograph reset.","uk":"Тахограф скинуто."}
            await q.edit_message_text(lbl.get(l,lbl["ru"]), reply_markup=kb_tacho(uid), parse_mode="Markdown")

    elif d.startswith("w_"):
        weight = float(d[2:])
        u["weight"] = weight
        city_from = u.get("from","")
        city_to   = u.get("to","")
        await q.edit_message_text(t["searching"], parse_mode="Markdown")
        result = await build_full_route_message(city_from, city_to, weight, l)
        await q.edit_message_text(
            result, reply_markup=kb_after_route(uid),
            parse_mode="Markdown", disable_web_page_preview=True)

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text.strip()
    u    = ud(uid); l = u["lang"]; t = T[l]
    step = u.get("step","")

    if step == "from":
        u["from"] = text; u["step"] = "to"
        await update.message.reply_text(t["ask_to"], reply_markup=kb_back(uid), parse_mode="Markdown")

    elif step == "to":
        u["to"] = text; u["step"] = "weight"
        await update.message.reply_text(t["ask_w"], reply_markup=kb_weight(uid), parse_mode="Markdown")

    elif step == "parking":
        await update.message.reply_text(t["search_parking"], parse_mode="Markdown")
        lon, lat, _, _ = await geocode(text)
        if not lon:
            await update.message.reply_text(t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        parkings = await find_tir_parkings_near(lat, lon, radius_km=60)
        if not parkings:
            await update.message.reply_text(t["no_parking"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        lines = []
        for i, p in enumerate(parkings[:5], 1):
            p_lat = p.get("lat") or p.get("center",{}).get("lat", lat)
            p_lon = p.get("lon") or p.get("center",{}).get("lon", lon)
            lines.append(f"*{i}.* {format_parking_short(p, lat, lon)}")
        await update.message.reply_text(
            "\n\n".join(lines), reply_markup=kb_back(uid),
            parse_mode="Markdown", disable_web_page_preview=True)

    elif step == "currency":
        amount, curr = parse_currency(text)
        if not amount or not curr:
            err = {"ru":"Формат: 100 CHF или 500 PLN","fr":"Format: 100 CHF ou 500 PLN","en":"Format: 100 CHF or 500 PLN","uk":"Формат: 100 CHF або 500 PLN"}
            await update.message.reply_text(err.get(l,err["ru"]), reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        result = convert_currency(amount, curr, l)
        await update.message.reply_text(
            f"*{amount} {curr}:*\n\n{result}", reply_markup=kb_back(uid), parse_mode="Markdown")

    else:
        u["step"] = ""
        await update.message.reply_text(t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")

async def location_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u   = ud(uid); l = u["lang"]; t = T[l]
    loc = update.message.location

    if u.get("step") == "parking":
        await update.message.reply_text(t["search_parking"], parse_mode="Markdown")
        parkings = await find_tir_parkings_near(loc.latitude, loc.longitude, radius_km=60)
        if not parkings:
            await update.message.reply_text(t["no_parking"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        lines = []
        for i, p in enumerate(parkings[:5], 1):
            lines.append(f"*{i}.* {format_parking_short(p, loc.latitude, loc.longitude)}")
        await update.message.reply_text(
            "\n\n".join(lines), reply_markup=kb_back(uid),
            parse_mode="Markdown", disable_web_page_preview=True)
    else:
        # Погода по геолокации
        weather_data = await get_weather_point(loc.latitude, loc.longitude)
        if weather_data:
            cur = weather_data.get("current", {})
            temp  = cur.get("temperature_2m","?")
            wind  = round(cur.get("wind_speed_10m",0))
            wcode = cur.get("weather_code",0)
            desc  = get_weather_desc(wcode, temp, l) if isinstance(temp, (int,float)) else str(temp)
            alert = check_weather_alert(weather_data, l)
            lbl = {"ru":"Погода в твоей точке","fr":"Météo à ta position","en":"Weather at your location","uk":"Погода у твоїй точці"}
            txt = f"*{lbl.get(l,lbl['ru'])}:*\n\n{desc}\nВетер: {wind} км/ч"
            if alert:
                txt += f"\n\n{alert}"
            await update.message.reply_text(txt, reply_markup=kb_back(uid), parse_mode="Markdown")

async def photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u   = ud(uid); l = u["lang"]; t = T[l]
    if u.get("step") != "cmr":
        await update.message.reply_text(t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")
        return
    await update.message.reply_text(t["ocr_proc"], parse_mode="Markdown")
    photo    = update.message.photo[-1]
    f_obj    = await ctx.bot.get_file(photo.file_id)
    bio      = await f_obj.download_as_bytearray()
    ocr_text = await do_ocr(bytes(bio))
    if not ocr_text:
        await update.message.reply_text(t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
        return
    address = extract_address(ocr_text)
    if address:
        u["to"] = address; u["step"] = "weight"
        await update.message.reply_text(
            f"*{t['addr_found']}:*\n`{address}`\n\n{t['ask_w']}",
            reply_markup=kb_weight(uid), parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"*{t['cmr_raw']}:*\n_{ocr_text[:400]}_\n\n{t['addr_none']}",
            reply_markup=kb_back(uid), parse_mode="Markdown")

# ─── ЗАПУСК ───────────────────────────────────────────────────────────────────
def main():
    if not TOKEN:
        logger.error("BOT_TOKEN не задан!")
        return
    logger.info(f"ORS-HGV:  {'OK' if ORS_KEY else 'OSRM fallback'}")
    logger.info(f"TomTom:   {'OK' if TOMTOM_KEY else 'disabled — no traffic'}")
    logger.info(f"OCR:      {'OK' if OCR_KEY else 'disabled'}")
    logger.info("Open-Meteo: OK (no key needed)")
    logger.info("Overpass:   OK (no key needed)")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("fuel",      cmd_fuel))
    app.add_handler(CommandHandler("rules",     cmd_rules))
    app.add_handler(CommandHandler("route",     cmd_route))
    app.add_handler(CommandHandler("parking",   cmd_parking))
    app.add_handler(CommandHandler("tacho",     cmd_tacho))
    app.add_handler(CommandHandler("bans",      cmd_bans))
    app.add_handler(CommandHandler("emergency", cmd_emergency))
    app.add_handler(CommandHandler("currency",  cmd_currency))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.PHOTO,    photo_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("GidTrack Navigator v1.0 запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
