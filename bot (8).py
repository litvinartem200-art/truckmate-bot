import os, logging, aiohttp, re, base64
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN   = os.environ.get("BOT_TOKEN", "")
OCR_KEY = os.environ.get("OCR_KEY", "")
ORS_KEY = os.environ.get("ORS_API_KEY", "")

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

# Телефоны экстренных служб по странам
EMERGENCY = {
    "FR":{"police":"17","ambulance":"15","fire":"18","eu":"112","road":"0800 207 207","note":"SAMU=15 VINCI autoroutes"},
    "DE":{"police":"110","ambulance":"112","fire":"112","eu":"112","road":"0800 5 00 40 35","note":"ADAC Pannenhilfe"},
    "IT":{"police":"113","ambulance":"118","fire":"115","eu":"112","road":"803 116","note":"ACI soccorso stradale"},
    "CH":{"police":"117","ambulance":"144","fire":"118","eu":"112","road":"140","note":"TCS Pannenhilfe"},
    "AT":{"police":"133","ambulance":"144","fire":"122","eu":"112","road":"120","note":"ÖAMTC"},
    "PL":{"police":"997","ambulance":"999","fire":"998","eu":"112","road":"19637","note":"PZMot pomoc drogowa"},
    "BE":{"police":"101","ambulance":"100","fire":"100","eu":"112","road":"0800 14 595","note":"Touring assistance"},
    "NL":{"police":"112","ambulance":"112","fire":"112","eu":"112","road":"088 269 2888","note":"ANWB hulp"},
    "ES":{"police":"091","ambulance":"061","fire":"080","eu":"112","road":"900 123 505","note":"DGT asistencia"},
    "CZ":{"police":"158","ambulance":"155","fire":"150","eu":"112","road":"1240","note":"ÚAMK silniční pomoc"},
    "HU":{"police":"107","ambulance":"104","fire":"105","eu":"112","road":"+36 188","note":"Magyar Autóklub"},
    "RO":{"police":"112","ambulance":"112","fire":"112","eu":"112","road":"9271","note":"ACR asistenta"},
}

# Запреты движения грузовиков по странам (упрощённая база)
BANS = {
    "FR": [
        "Пятница 22:00 — Суббота 22:00 (всегда)",
        "Суббота перед праздником 22:00 — Воскресенье 22:00",
        "1 янв, 8 май, 14 июл, 15 авг, 1 ноя, 25 дек — весь день",
    ],
    "DE": [
        "Воскресенье 00:00 — 22:00 (всегда)",
        "Праздничные дни 00:00 — 22:00",
        "Для опасных грузов — дополнительные ограничения",
    ],
    "IT": [
        "Суббота 14:00 — 22:00 (июнь-сентябрь 08:00-22:00)",
        "Воскресенье 07:00 — 22:00 (всегда)",
        "Праздники и канун праздников",
    ],
    "CH": [
        "Суббота 15:00 — Воскресенье 23:00",
        "Праздники 00:00 — 23:00",
        "Ночной запрет: 22:00 — 05:00 (каждый день!)",
    ],
    "AT": [
        "Воскресенье 00:00 — 22:00",
        "Праздники 00:00 — 22:00",
        "Ночной запрет на некоторых дорогах 22:00 — 05:00",
    ],
    "PL": [
        "Пятница 18:00 — Воскресенье 22:00 (июнь-сентябрь)",
        "Суббота 08:00 — Воскресенье 22:00 (октябрь-май)",
        "1 янв, Пасха, 3 май, 1 ноя, 11 ноя, 25-26 дек",
    ],
    "BE": [
        "Суббота 22:00 — Воскресенье 22:00",
        "Национальные праздники",
    ],
    "ES": [
        "Пятница 14:00 — Понедельник 00:00 (летом)",
        "Воскресенье 07:00 — 22:00 (круглый год)",
        "Праздники — уточнять по регионам",
    ],
}

# Конвертер валют (фиксированные курсы, обновлять раз в неделю)
RATES_EUR = {
    "CHF": 0.93, "PLN": 4.26, "CZK": 25.1, "HUF": 395.0,
    "RON": 4.97, "BGN": 1.96, "HRK": 7.53, "RSD": 117.0,
    "GBP": 1.17, "UAH": 43.5, "NOK": 11.8, "SEK": 11.4,
    "DKK": 7.46, "CHF": 0.93, "USD": 1.08,
}

def get_cons(w):
    if w <= 7.5:  return 18.0
    elif w <= 12: return 22.0
    elif w <= 20: return 28.0
    elif w <= 30: return 31.0
    return 34.0

udata = {}
def ud(uid):
    if uid not in udata:
        udata[uid] = {
            "lang":"ru","step":"","from":"","to":"","weight":20.0,
            "tacho_start": None,
            "tacho_daily": 0.0,
            "tacho_weekly": 0.0,
            "tacho_break_taken": False,
        }
    return udata[uid]

# ─── ТЕКСТЫ ──────────────────────────────────────────────────────────────────
T = {
"ru":{
    "welcome":"Привет! Я *GidTrack Pro* — полный помощник дальнобойщика Европы!\n\nВыбери язык:",
    "menu":"Главное меню GidTrack",
    "r_route":"Маршрут HGV + стоимость",
    "r_fuel":"Цены на дизель",
    "r_parking":"Стоянки TIR",
    "r_tacho":"Таймер тахографа",
    "r_border":"Документы / Границы",
    "r_bans":"Запреты движения",
    "r_emergency":"Экстренные номера",
    "r_currency":"Конвертер валют",
    "r_cmr":"Скан CMR",
    "r_rules":"Правила ЕС",
    "r_lang":"Язык",
    "r_pro":"Pro подписка",
    "r_back":"Назад",
    "ask_from":"Откуда едешь?\n_Примеры: Lyon, Berlin, Besancon_",
    "ask_to":"Куда едешь?",
    "ask_w":"Полный вес грузовика:",
    "w1":"до 7.5т","w2":"7.5—12т","w3":"12—20т","w4":"20—40т",
    "searching":"Прокладываю грузовой маршрут...",
    "not_found":"Не найдено. Проверь название.",
    "ask_parking":"Напиши город или отправь геолокацию.\nНайду ближайшие стоянки TIR:",
    "search_parking":"Ищу стоянки TIR...",
    "no_parking":"Стоянки не найдены в этом районе.",
    "ask_emergency":"Выбери страну для экстренных номеров:",
    "ask_bans":"Выбери страну для запретов движения:",
    "ask_currency":"Напиши сумму и валюту:\n_Пример: 100 CHF или 500 PLN_",
    "tacho_menu":"Таймер тахографа:",
    "tacho_start_btn":"Старт вождения",
    "tacho_stop_btn":"Остановка",
    "tacho_status_btn":"Статус",
    "tacho_reset_btn":"Сброс",
    "tacho_started":"Таймер запущен!\nПо регламенту ЕС (561/2006):\n• Максимум без перерыва: 4.5 ч\n• Перерыв: 45 мин\nПришлю предупреждение за 15 мин до лимита.",
    "tacho_already":"Таймер уже запущен! Нажми Остановка сначала.",
    "tacho_stopped":"Остановка зафиксирована.",
    "tacho_not_started":"Таймер не запущен.",
    "ask_cmr":"Отправь фото CMR накладной:",
    "ocr_proc":"Читаю документ...",
    "ocr_nokey":"OCR недоступен. Добавь OCR_KEY в Railway.",
    "new_route":"Новый маршрут",
    "addr_found":"Адрес из CMR",
    "addr_none":"Адрес не найден. Введи вручную.",
    "cmr_raw":"Текст CMR",
    "lbl_hgv":"Грузовой маршрут (ORS-HGV)",
    "lbl_std":"Стандартный маршрут (OSRM)",
    "lbl_dist":"Расстояние","lbl_time":"Время",
    "lbl_weight":"Вес","lbl_cons":"Расход",
    "lbl_fuel":"Топливо","lbl_toll":"Платные дороги",
    "lbl_vign":"Виньетка CH","lbl_total":"ИТОГО",
    "lbl_tip":"Совет: заправься в","lbl_save":"экономия",
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
        "• Ежедневный — 11 ч\n• Еженедельный — 45 ч\n\n"
        "*Запреты движения:*\n"
        "Франция: Пт 22:00—Сб 22:00\nГермания: Вс + праздники\n"
        "Италия: Сб 14:00—Вс 22:00\nШвейцария: Сб 15:00—Вс 23:00\n"
        "Австрия: Вс 00:00—22:00\nПольша: Пт 18:00—Вс 22:00 (лето)"
    ),
    "b_ask":"Выбери страну:",
    "pro_text":(
        "*GidTrack Pro — 7€/месяц*\n\n"
        "Бесплатно: 3 маршрута, цены дизеля, правила\n\n"
        "Pro:\n• Неограниченные маршруты HGV\n"
        "• Стоянки TIR по маршруту\n• Таймер тахографа\n"
        "• Погода по маршруту\n• Скан CMR\n"
        "• Запреты + алерты\n• Экстренные номера 30 стран\n"
        "• Конвертер валют\n• Поддержка 24/7\n\n"
        "Оформить: @gidtrack_support"
    ),
    "help_text":(
        "*GidTrack — команды:*\n\n"
        "/start — меню\n/route — маршрут\n/fuel — цены дизеля\n"
        "/parking — стоянки TIR\n/tacho — тахограф\n"
        "/bans — запреты движения\n/emergency — экстренные номера\n"
        "/currency — конвертер валют\n/rules — правила ЕС\n/help — справка"
    ),
},
"fr":{
    "welcome":"Bonjour! Je suis *GidTrack Pro* — assistant complet pour chauffeurs!\n\nChoisis ta langue:",
    "menu":"Menu GidTrack",
    "r_route":"Itinéraire HGV + coût",
    "r_fuel":"Prix diesel",
    "r_parking":"Parkings TIR",
    "r_tacho":"Minuteur tachygraphe",
    "r_border":"Documents / Frontières",
    "r_bans":"Interdictions de circuler",
    "r_emergency":"Numéros d'urgence",
    "r_currency":"Convertisseur devises",
    "r_cmr":"Scanner CMR",
    "r_rules":"Règles UE",
    "r_lang":"Langue",
    "r_pro":"Abonnement Pro",
    "r_back":"Retour",
    "ask_from":"Ville de départ?\n_Exemples: Lyon, Berlin, Besancon_",
    "ask_to":"Ville d'arrivée?",
    "ask_w":"Poids total camion:",
    "w1":"7.5t","w2":"7.5—12t","w3":"12—20t","w4":"20—40t",
    "searching":"Calcul itinéraire PL...",
    "not_found":"Non trouvé. Vérifie le nom.",
    "ask_parking":"Ecris une ville ou envoie ta position.\nJe trouve les parkings TIR proches:",
    "search_parking":"Recherche parkings TIR...",
    "no_parking":"Aucun parking TIR trouvé dans cette zone.",
    "ask_emergency":"Choisis le pays pour les numéros d'urgence:",
    "ask_bans":"Choisis le pays pour les interdictions:",
    "ask_currency":"Ecris le montant et la devise:\n_Exemple: 100 CHF ou 500 PLN_",
    "tacho_menu":"Minuteur tachygraphe:",
    "tacho_start_btn":"Démarrer conduite",
    "tacho_stop_btn":"Arrêt",
    "tacho_status_btn":"Statut",
    "tacho_reset_btn":"Réinitialiser",
    "tacho_started":"Minuteur démarré!\nRèglements UE (561/2006):\n• Max sans pause: 4.5h\n• Pause: 45min\nJe t'avertis 15min avant la limite.",
    "tacho_already":"Minuteur déjà démarré! Appuie sur Arrêt d'abord.",
    "tacho_stopped":"Arrêt enregistré.",
    "tacho_not_started":"Minuteur non démarré.",
    "ask_cmr":"Envoie une photo CMR:",
    "ocr_proc":"Lecture du document...",
    "ocr_nokey":"OCR indisponible. Ajoute OCR_KEY dans Railway.",
    "new_route":"Nouvel itinéraire",
    "addr_found":"Adresse CMR",
    "addr_none":"Adresse non trouvée. Saisis manuellement.",
    "cmr_raw":"Texte CMR",
    "lbl_hgv":"Itinéraire PL (ORS-HGV)",
    "lbl_std":"Itinéraire standard (OSRM)",
    "lbl_dist":"Distance","lbl_time":"Durée",
    "lbl_weight":"Poids","lbl_cons":"Conso",
    "lbl_fuel":"Carburant","lbl_toll":"Péages",
    "lbl_vign":"Vignette CH","lbl_total":"TOTAL",
    "lbl_tip":"Conseil: fais le plein en","lbl_save":"économie",
    "fuel_prices":"*Prix diesel Europe*\n\nPas cher: Pologne 1.41€, Slovaquie 1.48€\nMoyens: France 1.65€, Allemagne 1.71€\nCher: Suisse 1.89€, Italie 1.95€",
    "rules_text":"*Règles UE 561/2006*\n\nJour: max 9h\nSemaine: max 56h\nPause après 4.5h: 45min\nRepos quotidien: 11h",
    "b_ask":"Choisis le pays:",
    "pro_text":"*GidTrack Pro — 7€/mois*\n\nItinéraires illimités, parkings TIR, tachygraphe, urgences 30 pays\n\nAbonnement: @gidtrack_support",
    "help_text":"*Commandes:*\n\n/route /fuel /parking /tacho /bans /emergency /currency /rules",
},
"en":{
    "welcome":"Hi! I'm *GidTrack Pro* — the complete European truck driver assistant!\n\nChoose language:",
    "menu":"GidTrack Menu",
    "r_route":"HGV Route + cost",
    "r_fuel":"Diesel prices",
    "r_parking":"TIR parkings",
    "r_tacho":"Tachograph timer",
    "r_border":"Documents / Borders",
    "r_bans":"Driving bans",
    "r_emergency":"Emergency numbers",
    "r_currency":"Currency converter",
    "r_cmr":"Scan CMR",
    "r_rules":"EU rules",
    "r_lang":"Language",
    "r_pro":"Pro subscription",
    "r_back":"Back",
    "ask_from":"Where departing from?\n_Examples: Lyon, Berlin, Besancon_",
    "ask_to":"Where going to?",
    "ask_w":"Total truck weight:",
    "w1":"7.5t","w2":"7.5—12t","w3":"12—20t","w4":"20—40t",
    "searching":"Calculating HGV route...",
    "not_found":"Not found. Check the name.",
    "ask_parking":"Type a city or send location.\nI'll find nearby TIR parkings:",
    "search_parking":"Searching TIR parkings...",
    "no_parking":"No TIR parkings found in this area.",
    "ask_emergency":"Choose country for emergency numbers:",
    "ask_bans":"Choose country for driving bans:",
    "ask_currency":"Type amount and currency:\n_Example: 100 CHF or 500 PLN_",
    "tacho_menu":"Tachograph timer:",
    "tacho_start_btn":"Start driving",
    "tacho_stop_btn":"Stop",
    "tacho_status_btn":"Status",
    "tacho_reset_btn":"Reset",
    "tacho_started":"Timer started!\nEU rules (561/2006):\n• Max without break: 4.5h\n• Break: 45min\nI'll alert you 15min before the limit.",
    "tacho_already":"Timer already running! Press Stop first.",
    "tacho_stopped":"Stop recorded.",
    "tacho_not_started":"Timer not started.",
    "ask_cmr":"Send CMR photo:",
    "ocr_proc":"Reading document...",
    "ocr_nokey":"OCR unavailable. Add OCR_KEY to Railway.",
    "new_route":"New route",
    "addr_found":"CMR address",
    "addr_none":"Address not found. Enter manually.",
    "cmr_raw":"CMR text",
    "lbl_hgv":"HGV route (ORS-HGV)",
    "lbl_std":"Standard route (OSRM)",
    "lbl_dist":"Distance","lbl_time":"Time",
    "lbl_weight":"Weight","lbl_cons":"Consumption",
    "lbl_fuel":"Fuel","lbl_toll":"Tolls",
    "lbl_vign":"CH Vignette","lbl_total":"TOTAL",
    "lbl_tip":"Tip: fill up in","lbl_save":"save",
    "fuel_prices":"*Diesel prices Europe*\n\nCheap: Poland 1.41€, Slovakia 1.48€\nAverage: France 1.65€, Germany 1.71€\nExpensive: Switzerland 1.89€, Italy 1.95€",
    "rules_text":"*EU Rules 561/2006*\n\nDay: max 9h\nWeek: max 56h\nBreak after 4.5h: 45min\nDaily rest: 11h",
    "b_ask":"Choose country:",
    "pro_text":"*GidTrack Pro — €7/month*\n\nUnlimited HGV routes, TIR parkings, tachograph, emergencies 30 countries\n\nSubscribe: @gidtrack_support",
    "help_text":"*Commands:*\n\n/route /fuel /parking /tacho /bans /emergency /currency /rules",
},
"uk":{
    "welcome":"Привіт! Я *GidTrack Pro* — повний помічник далекобійника!\n\nОбери мову:",
    "menu":"Головне меню GidTrack",
    "r_route":"Маршрут HGV + вартість",
    "r_fuel":"Ціни на дизель",
    "r_parking":"Стоянки TIR",
    "r_tacho":"Таймер тахографа",
    "r_border":"Документи / Кордони",
    "r_bans":"Заборони руху",
    "r_emergency":"Екстрені номери",
    "r_currency":"Конвертер валют",
    "r_cmr":"Скан CMR",
    "r_rules":"Правила ЄС",
    "r_lang":"Мова",
    "r_pro":"Pro підписка",
    "r_back":"Назад",
    "ask_from":"Звідки їдеш?\n_Приклади: Lyon, Berlin, Besancon_",
    "ask_to":"Куди їдеш?",
    "ask_w":"Повна вага вантажівки:",
    "w1":"до 7.5т","w2":"7.5—12т","w3":"12—20т","w4":"20—40т",
    "searching":"Прокладаю вантажний маршрут...",
    "not_found":"Не знайдено. Перевір назву.",
    "ask_parking":"Напиши місто або відправ геолокацію.\nЗнайду стоянки TIR:",
    "search_parking":"Шукаю стоянки TIR...",
    "no_parking":"Стоянок TIR не знайдено.",
    "ask_emergency":"Обери країну для екстрених номерів:",
    "ask_bans":"Обери країну для заборон руху:",
    "ask_currency":"Напиши суму і валюту:\n_Приклад: 100 CHF або 500 PLN_",
    "tacho_menu":"Таймер тахографа:",
    "tacho_start_btn":"Старт водіння",
    "tacho_stop_btn":"Зупинка",
    "tacho_status_btn":"Статус",
    "tacho_reset_btn":"Скинути",
    "tacho_started":"Таймер запущено!\nПравила ЄС (561/2006):\n• Максимум без перерви: 4.5 год\n• Перерва: 45 хв\nПовідомлю за 15 хв до ліміту.",
    "tacho_already":"Таймер вже запущено! Спочатку натисни Зупинка.",
    "tacho_stopped":"Зупинку зафіксовано.",
    "tacho_not_started":"Таймер не запущено.",
    "ask_cmr":"Відправ фото CMR:",
    "ocr_proc":"Читаю документ...",
    "ocr_nokey":"OCR недоступний. Додай OCR_KEY у Railway.",
    "new_route":"Новий маршрут",
    "addr_found":"Адреса з CMR",
    "addr_none":"Адресу не знайдено. Введи вручну.",
    "cmr_raw":"Текст CMR",
    "lbl_hgv":"Вантажний маршрут (ORS-HGV)",
    "lbl_std":"Стандартний маршрут (OSRM)",
    "lbl_dist":"Відстань","lbl_time":"Час",
    "lbl_weight":"Вага","lbl_cons":"Витрата",
    "lbl_fuel":"Пальне","lbl_toll":"Платні дороги",
    "lbl_vign":"Víньєтка CH","lbl_total":"РАЗОМ",
    "lbl_tip":"Порада: заправся в","lbl_save":"економія",
    "fuel_prices":"*Ціни на дизель Європа*\n\nДешево: Польща 1.41€, Словаччина 1.48€\nСередні: Франція 1.65€, Австрія 1.68€\nДорого: Швейцарія 1.89€, Iталія 1.95€",
    "rules_text":"*Правила ЄС 561/2006*\n\nДень: до 9г\nТиждень: до 56г\nПісля 4.5г — 45хв\nЩодобовий відпочинок: 11г",
    "b_ask":"Обери країну:",
    "pro_text":"*GidTrack Pro — 7€/місяць*\n\nНеобмежені маршрути, стоянки TIR, тахограф, екстрені номери 30 країн\n\nОформити: @gidtrack_support",
    "help_text":"*Команди:*\n\n/route /fuel /parking /tacho /bans /emergency /currency /rules",
},
}

BORDER = {
"CH":{"ru":"*ШВЕЙЦАРИЯ*\n\n• CMR\n• Права CE + картка\n• Техпаспорт + Зелёная карта\n• Виньетка 40 CHF!\n• ЕКМТ\n\nТаможня! Запрет: ночь 22-05, воскресенье","fr":"*SUISSE*\n\n• CMR\n• Permis CE + carte\n• Carte grise + Verte\n• Vignette 40 CHF!\n• CEMT\n\nDouane! Nuit 22h-05h, dimanche interdits","en":"*SWITZERLAND*\n\n• CMR\n• CE license + card\n• Reg + Green Card\n• Vignette 40 CHF!\n• ECMT\n\nCustoms! Night 22-05, Sunday ban","uk":"*ШВЕЙЦАРІЯ*\n\n• CMR\n• Права CE + картка\n• Техпаспорт + Зелена картка\n• Víньєтка 40 CHF!\n• ЄКМТ\n\nМитниця! Заборона: ніч 22-05, неділя"},
"DE":{"ru":"*ГЕРМАНИЯ*\n\n• CMR\n• Права CE + карточка\n• Техпаспорт + Зелёная карта\n• Maut toll-collect.de (7.5т+!)\n\nЗапрет: Вс 00-22 + праздники\nEuro 4 в зонах LEZ","fr":"*ALLEMAGNE*\n\n• CMR\n• Permis CE + carte\n• Carte grise + Verte\n• Maut toll-collect.de (7.5t+!)\n\nInterdiction: dim 00h-22h + fériés","en":"*GERMANY*\n\n• CMR\n• CE license + card\n• Reg + Green Card\n• Maut toll-collect.de (7.5t+!)\n\nBan: Sun 00-22 + holidays\nEuro 4 in LEZ","uk":"*НIМЕЧЧИНА*\n\n• CMR\n• Права CE + картка\n• Техпаспорт + Зелена картка\n• Maut toll-collect.de (7.5т+!)\n\nЗаборона: нд 00-22 + свята"},
"IT":{"ru":"*ИТАЛИЯ*\n\n• CMR\n• Права CE + карточка\n• Техпаспорт + Зелёная карта\n• Autostrada — платные\n\nЗапрет: Сб 14-22, Вс 07-22\nЗоны ZTL — штрафы!","fr":"*ITALIE*\n\n• CMR\n• Permis CE + carte\n• Carte grise + Verte\n• Autostrade payantes\n\nInterdiction: Sam 14h-22h, Dim 07h-22h\nZones ZTL — amendes!","en":"*ITALY*\n\n• CMR\n• CE license + card\n• Reg + Green Card\n• Autostrade tolls\n\nBan: Sat 14-22, Sun 07-22\nZTL zones — fines!","uk":"*IТАЛІЯ*\n\n• CMR\n• Права CE + картка\n• Техпаспорт + Зелена картка\n• Autostrada платна\n\nЗаборона: Сб 14-22, Нд 07-22\nЗони ZTL — штрафи!"},
"FR":{"ru":"*ФРАНЦИЯ*\n\n• CMR\n• Права CE + карточка\n• Техпаспорт + Зелёная карта\n• Péage платные\n• Crit'Air в городах\n\nЗапрет: Пт 22:00—Сб 22:00","fr":"*FRANCE*\n\n• CMR\n• Permis CE + carte\n• Carte grise + Verte\n• Péage\n• Crit'Air en ville\n\nInterdiction: Ven 22h—Sam 22h","en":"*FRANCE*\n\n• CMR\n• CE license + card\n• Reg + Green Card\n• Péage tolls\n• Crit'Air in cities\n\nBan: Fri 22:00—Sat 22:00","uk":"*ФРАНЦІЯ*\n\n• CMR\n• Права CE + картка\n• Техпаспорт + Зелена картка\n• Péage платний\n• Crit'Air у містах\n\nЗаборона: Пт 22:00—Сб 22:00"},
"AT":{"ru":"*АВСТРИЯ*\n\n• CMR\n• Права CE + карточка\n• Техпаспорт + Зелёная карта\n• Maut go-maut.at (3.5т+)\n\nЗапрет: Вс 00-22\nНочь: ограничение 80 км/ч","fr":"*AUTRICHE*\n\n• CMR\n• Permis CE + carte\n• Carte grise + Verte\n• Maut go-maut.at (3.5t+)\n\nInterdiction: dim 00h-22h","en":"*AUSTRIA*\n\n• CMR\n• CE license + card\n• Reg + Green Card\n• Maut go-maut.at (3.5t+)\n\nBan: Sun 00-22\nNight limit 80 km/h","uk":"*АВСТРІЯ*\n\n• CMR\n• Права CE + картка\n• Техпаспорт + Зелена картка\n• Maut go-maut.at (3.5т+)\n\nЗаборона: нд 00-22"},
"PL":{"ru":"*ПОЛЬША*\n\n• CMR\n• Права CE + карточка\n• Техпаспорт + Зелёная карта\n• e-TOLL etoll.gov.pl (обязателен!)\n\nЗапрет: Пт 18—Вс 22 (лето)\nviaTOLL отменён!","fr":"*POLOGNE*\n\n• CMR\n• Permis CE + carte\n• Carte grise + Verte\n• e-TOLL etoll.gov.pl (obligatoire!)\n\nInterdiction: Ven 18h—Dim 22h (été)","en":"*POLAND*\n\n• CMR\n• CE license + card\n• Reg + Green Card\n• e-TOLL etoll.gov.pl (mandatory!)\n\nBan: Fri 18—Sun 22 (summer)","uk":"*ПОЛЬЩА*\n\n• CMR\n• Права CE + картка\n• Техпаспорт + Зелена картка\n• e-TOLL etoll.gov.pl (обов'язковий!)\n\nЗаборона: Пт 18—Нд 22 (літо)"},
}

CNAMES = {
    "ru":{"BG":"Болгарія","UA":"Украина","RO":"Румыния","PL":"Польша","SK":"Словакия","LU":"Люксембург"},
    "uk":{"BG":"Болгарія","UA":"Україна","RO":"Румунія","PL":"Польща","SK":"Словаччина","LU":"Люксембург"},
    "fr":{"BG":"Bulgarie","UA":"Ukraine","RO":"Roumanie","PL":"Pologne","SK":"Slovaquie","LU":"Luxembourg"},
    "en":{"BG":"Bulgaria","UA":"Ukraine","RO":"Romania","PL":"Poland","SK":"Slovakia","LU":"Luxembourg"},
}

# ─── API ФУНКЦИИ ─────────────────────────────────────────────────────────────
async def geocode(city):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q":city,"format":"json","limit":1,"addressdetails":1},
                headers={"User-Agent":"GidTrackBot/6.0 contact@gidtrack.eu"},
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

async def get_route_ors(lon1, lat1, lon2, lat2, weight_t):
    if not ORS_KEY: return None, None
    try:
        payload = {
            "coordinates":[[lon1,lat1],[lon2,lat2]], "units":"km",
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
                timeout=aiohttp.ClientTimeout(total=20)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    seg = data["routes"][0]["summary"]
                    km = round(seg["distance"])
                    h, m = divmod(round(seg["duration"]/60), 60)
                    return km, f"{h}h{m:02d}" if m else f"{h}h"
    except Exception as e:
        logger.error(f"ORS: {e}")
    return None, None

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
                    return km, f"{h}h{m:02d}" if m else f"{h}h"
    except Exception as e:
        logger.error(f"OSRM: {e}")
    return None, None

async def smart_route(lon1, lat1, lon2, lat2, weight_t):
    if ORS_KEY:
        km, dur = await get_route_ors(lon1, lat1, lon2, lat2, weight_t)
        if km: return km, dur, "HGV"
    km, dur = await get_route_osrm(lon1, lat1, lon2, lat2)
    if km: return km, dur, "STD"
    return None, None, None

async def find_tir_parkings(lat, lon, radius_km=50):
    """Ищет стоянки для грузовиков через Overpass API (OpenStreetMap)"""
    try:
        r_m = radius_km * 1000
        query = f"""
[out:json][timeout:25];
(
  node["amenity"="truck_stop"](around:{r_m},{lat},{lon});
  node["amenity"="parking"]["hgv"="yes"](around:{r_m},{lat},{lon});
  node["amenity"="parking"]["hgv"="designated"](around:{r_m},{lat},{lon});
  way["amenity"="truck_stop"](around:{r_m},{lat},{lon});
  way["amenity"="parking"]["hgv"="yes"](around:{r_m},{lat},{lon});
);
out center 8;
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

def format_parking(p, user_lat, user_lon, lang):
    tags = p.get("tags", {})
    clat = p.get("lat") or p.get("center",{}).get("lat", user_lat)
    clon = p.get("lon") or p.get("center",{}).get("lon", user_lon)
    name = tags.get("name") or tags.get("operator") or ("Truck Stop" if lang=="en" else "Стоянка TIR")
    amenities = []
    if tags.get("shower") == "yes":      amenities.append("Душ")
    if tags.get("toilets"):              amenities.append("WC")
    if tags.get("restaurant") == "yes" or tags.get("food") == "yes": amenities.append("Кафе")
    if tags.get("security") in ("yes","guard","camera"): amenities.append("Охрана")
    if tags.get("wifi") == "yes":        amenities.append("WiFi")
    fee = tags.get("fee","")
    fee_str = "" if not fee else (" Бесплатно" if fee=="no" else " Платная")
    am_str = " · ".join(amenities) if amenities else ""
    maps_url = f"https://maps.google.com/?q={clat},{clon}"
    return f"*{name}*{fee_str}\n{am_str}\n{maps_url}"

async def get_weather(lat, lon):
    """Погода через Open-Meteo — без ключа, бесплатно"""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat, "longitude": lon,
                    "current": "temperature_2m,wind_speed_10m,weather_code,visibility",
                    "hourly": "temperature_2m,precipitation,wind_speed_10m",
                    "forecast_days": 1, "timezone": "auto",
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                return await r.json()
    except Exception as e:
        logger.error(f"weather: {e}")
    return None

def weather_alert(data, lang="ru"):
    if not data: return ""
    cur = data.get("current", {})
    temp  = cur.get("temperature_2m", 0)
    wind  = cur.get("wind_speed_10m", 0)
    wcode = cur.get("weather_code", 0)
    vis   = cur.get("visibility", 10000)
    alerts = []
    if temp <= 0 and wcode in range(51,68): alerts.append("Гололёд!" if lang=="ru" else "Black ice!" if lang=="en" else "Verglas!")
    if wind >= 60: alerts.append(f"Сильный ветер {round(wind)} км/ч!" if lang=="ru" else f"Strong wind {round(wind)} km/h!" if lang=="en" else f"Vent fort {round(wind)} km/h!")
    if vis and vis < 200: alerts.append("Туман!" if lang=="ru" else "Fog!" if lang=="en" else "Brouillard!")
    if wcode in range(95,100): alerts.append("Гроза!" if lang=="ru" else "Thunderstorm!" if lang=="en" else "Orage!")
    if alerts:
        return "\n" + ("ВНИМАНИЕ: " if lang=="ru" else "WARNING: " if lang=="en" else "ATTENTION: ") + " ".join(alerts)
    return ""

async def do_ocr(photo_bytes):
    if not OCR_KEY: return None
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

def extract_address(text):
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

def parse_currency(text):
    """100 CHF → (100, CHF)"""
    m = re.search(r'(\d+[\.,]?\d*)\s*([A-Z]{3})', text.upper())
    if not m:
        m = re.search(r'([A-Z]{3})\s*(\d+[\.,]?\d*)', text.upper())
        if m: return float(m.group(2).replace(",",".")), m.group(1)
        return None, None
    return float(m.group(1).replace(",",".")), m.group(2)

def convert_currency(amount, from_curr, lang="ru"):
    if from_curr == "EUR":
        lines = []
        for curr, rate in sorted(RATES_EUR.items()):
            val = round(amount * rate)
            lines.append(f"{curr}: {val}")
        return "\n".join(lines[:8])
    rate = RATES_EUR.get(from_curr)
    if not rate:
        return "Валюта не найдена" if lang=="ru" else "Currency not found"
    eur = round(amount / rate, 2)
    lines = [f"{amount} {from_curr} = *{eur} EUR*", ""]
    for curr, r in sorted(RATES_EUR.items()):
        if curr != from_curr:
            val = round(eur * r)
            lines.append(f"{curr}: {val}")
    return "\n".join(lines[:10])

def tacho_status(u, lang="ru"):
    start = u.get("tacho_start")
    if not start:
        return "Таймер не запущен" if lang=="ru" else "Timer not started" if lang=="en" else "Minuteur non démarré" if lang=="fr" else "Таймер не запущено"
    elapsed = (datetime.now() - start).total_seconds() / 3600
    remaining = max(0, 4.5 - elapsed)
    daily_total = u.get("tacho_daily", 0) + elapsed
    weekly_total = u.get("tacho_weekly", 0) + daily_total
    if lang == "ru":
        return (
            f"*Тахограф — статус*\n\n"
            f"Едешь: *{elapsed:.1f} ч*\n"
            f"До перерыва: *{remaining:.1f} ч*\n"
            f"День итого: *{daily_total:.1f} / 9 ч*\n"
            f"Неделя итого: *{weekly_total:.1f} / 56 ч*\n\n"
            f"{'НУЖЕН ПЕРЕРЫВ 45 МИН!' if remaining <= 0 else ('Осталось ' + f'{remaining:.1f} ч до перерыва')}"
        )
    elif lang == "fr":
        return (
            f"*Tachygraphe — statut*\n\n"
            f"Conduite: *{elapsed:.1f}h*\n"
            f"Avant pause: *{remaining:.1f}h*\n"
            f"Journée: *{daily_total:.1f} / 9h*\n"
            f"Semaine: *{weekly_total:.1f} / 56h*\n\n"
            f"{'PAUSE OBLIGATOIRE 45 MIN!' if remaining <= 0 else f'Encore {remaining:.1f}h avant pause'}"
        )
    elif lang == "uk":
        return (
            f"*Тахограф — статус*\n\n"
            f"Їдеш: *{elapsed:.1f} год*\n"
            f"До перерви: *{remaining:.1f} год*\n"
            f"День всього: *{daily_total:.1f} / 9 год*\n"
            f"Тиждень: *{weekly_total:.1f} / 56 год*\n\n"
            f"{'ПОТРІБНА ПЕРЕРВА 45 ХВ!' if remaining <= 0 else f'Ще {remaining:.1f} год до перерви'}"
        )
    else:
        return (
            f"*Tachograph — status*\n\n"
            f"Driving: *{elapsed:.1f}h*\n"
            f"Before break: *{remaining:.1f}h*\n"
            f"Day total: *{daily_total:.1f} / 9h*\n"
            f"Week total: *{weekly_total:.1f} / 56h*\n\n"
            f"{'MANDATORY BREAK 45 MIN!' if remaining <= 0 else f'{remaining:.1f}h left before break'}"
        )

def build_cost(km, cc1, cc2, weight, lang, rtype="STD"):
    t = T[lang]
    cons = get_cons(weight)
    fp = round((DIESEL.get(cc1,1.65) + DIESEL.get(cc2,1.65)) / 2, 2)
    fl = round(km * cons / 100)
    fc = round(fl * fp)
    if cc1=="CH" or cc2=="CH":
        toll, tlbl = CH_VIGNETTE, t["lbl_vign"]
    else:
        toll = round(km * max(TOLL.get(cc1,10), TOLL.get(cc2,10)) / 100)
        tlbl = t["lbl_toll"]
    total = fc + toll
    cheapest = min(DIESEL, key=DIESEL.get)
    saving = round(fl * (fp - DIESEL[cheapest]))
    cname = CNAMES.get(lang, CNAMES["en"]).get(cheapest, cheapest)
    rlbl = t["lbl_hgv"] if rtype=="HGV" else t["lbl_std"]
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

# ─── КЛАВИАТУРЫ ──────────────────────────────────────────────────────────────
def kb_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Українська",callback_data="lang_uk"),
         InlineKeyboardButton("Русский",   callback_data="lang_ru")],
        [InlineKeyboardButton("Français",  callback_data="lang_fr"),
         InlineKeyboardButton("English",   callback_data="lang_en")],
    ])

def kb_menu(uid):
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

def kb_back(uid):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(T[ud(uid)["lang"]]["r_back"], callback_data="back")
    ]])

def kb_weight(uid):
    t = T[ud(uid)["lang"]]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["w1"],callback_data="w_7.5"),
         InlineKeyboardButton(t["w2"],callback_data="w_12")],
        [InlineKeyboardButton(t["w3"],callback_data="w_20"),
         InlineKeyboardButton(t["w4"],callback_data="w_40")],
        [InlineKeyboardButton(t["r_back"],callback_data="back")],
    ])

def kb_border(uid):
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

def kb_bans(uid):
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

def kb_emergency(uid):
    t = T[ud(uid)["lang"]]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Франция", callback_data="em_FR"),
         InlineKeyboardButton("Германия", callback_data="em_DE"),
         InlineKeyboardButton("Италия", callback_data="em_IT")],
        [InlineKeyboardButton("Швейцария", callback_data="em_CH"),
         InlineKeyboardButton("Австрия", callback_data="em_AT"),
         InlineKeyboardButton("Польша", callback_data="em_PL")],
        [InlineKeyboardButton("Бельгия", callback_data="em_BE"),
         InlineKeyboardButton("Нидерланды", callback_data="em_NL"),
         InlineKeyboardButton("Испания", callback_data="em_ES")],
        [InlineKeyboardButton("Чехия", callback_data="em_CZ"),
         InlineKeyboardButton("Венгрия", callback_data="em_HU"),
         InlineKeyboardButton("Румыния", callback_data="em_RO")],
        [InlineKeyboardButton(t["r_back"], callback_data="back")],
    ])

def kb_tacho(uid):
    t = T[ud(uid)["lang"]]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["tacho_start_btn"],  callback_data="tacho_start"),
         InlineKeyboardButton(t["tacho_stop_btn"],   callback_data="tacho_stop")],
        [InlineKeyboardButton(t["tacho_status_btn"], callback_data="tacho_status"),
         InlineKeyboardButton(t["tacho_reset_btn"],  callback_data="tacho_reset")],
        [InlineKeyboardButton(t["r_back"], callback_data="back")],
    ])

def kb_after(uid):
    t = T[ud(uid)["lang"]]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["new_route"],  callback_data="m_route")],
        [InlineKeyboardButton(t["r_border"],   callback_data="m_border"),
         InlineKeyboardButton(t["r_fuel"],     callback_data="m_fuel")],
        [InlineKeyboardButton(t["r_parking"],  callback_data="m_parking"),
         InlineKeyboardButton(t["r_bans"],     callback_data="m_bans")],
        [InlineKeyboardButton(t["r_back"],     callback_data="back")],
    ])

# ─── ХЭНДЛЕРЫ ────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud(uid)["step"] = ""
    await update.message.reply_text(T["ru"]["welcome"], reply_markup=kb_lang(), parse_mode="Markdown")

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(T[ud(uid)["lang"]]["help_text"], reply_markup=kb_back(uid), parse_mode="Markdown")

async def cmd_fuel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(T[ud(uid)["lang"]]["fuel_prices"], reply_markup=kb_back(uid), parse_mode="Markdown")

async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(T[ud(uid)["lang"]]["rules_text"], reply_markup=kb_back(uid), parse_mode="Markdown")

async def cmd_route(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud(uid)["step"] = "from"
    await update.message.reply_text(T[ud(uid)["lang"]]["ask_from"], reply_markup=kb_back(uid), parse_mode="Markdown")

async def cmd_parking(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud(uid)["step"] = "parking"
    await update.message.reply_text(T[ud(uid)["lang"]]["ask_parking"], reply_markup=kb_back(uid), parse_mode="Markdown")

async def cmd_tacho(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    l = ud(uid)["lang"]
    await update.message.reply_text(T[l]["tacho_menu"], reply_markup=kb_tacho(uid), parse_mode="Markdown")

async def cmd_bans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(T[ud(uid)["lang"]]["ask_bans"], reply_markup=kb_bans(uid), parse_mode="Markdown")

async def cmd_emergency(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(T[ud(uid)["lang"]]["ask_emergency"], reply_markup=kb_emergency(uid), parse_mode="Markdown")

async def cmd_currency(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud(uid)["step"] = "currency"
    await update.message.reply_text(T[ud(uid)["lang"]]["ask_currency"], reply_markup=kb_back(uid), parse_mode="Markdown")

async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = ud(uid); l = u["lang"]; t = T[l]
    d = q.data

    if d.startswith("lang_"):
        u["lang"] = d[5:]; l = u["lang"]; t = T[l]; u["step"] = ""
        await q.edit_message_text(t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")

    elif d in ("back","m_lang"):
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

    elif d == "m_parking":
        u["step"] = "parking"
        await q.edit_message_text(t["ask_parking"], reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d == "m_currency":
        u["step"] = "currency"
        await q.edit_message_text(t["ask_currency"], reply_markup=kb_back(uid), parse_mode="Markdown")

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
        flag_names = {"FR":"Франция","DE":"Германия","IT":"Италия","CH":"Швейцария",
                     "AT":"Австрия","PL":"Польша","BE":"Бельгия","ES":"Испания"}
        name = flag_names.get(cc, cc)
        await q.edit_message_text(
            f"*{name} — запреты движения*\n\n{bans_text}",
            reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d.startswith("em_"):
        cc = d[3:]
        em = EMERGENCY.get(cc, {})
        if em:
            lines = [
                f"*Экстренные номера — {cc}*\n",
                f"Полиция: *{em.get('police','112')}*",
                f"Скорая: *{em.get('ambulance','112')}*",
                f"Пожарные: *{em.get('fire','112')}*",
                f"ЕС единый: *{em.get('eu','112')}*",
                f"Помощь на дороге: *{em.get('road','')}*",
                f"\n_{em.get('note','')}_",
            ]
            await q.edit_message_text("\n".join(lines), reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d.startswith("tacho_"):
        action = d[6:]
        if action == "start":
            if u.get("tacho_start"):
                await q.edit_message_text(t["tacho_already"], reply_markup=kb_tacho(uid), parse_mode="Markdown")
            else:
                u["tacho_start"] = datetime.now()
                u["tacho_break_taken"] = False
                await q.edit_message_text(t["tacho_started"], reply_markup=kb_tacho(uid), parse_mode="Markdown")
        elif action == "stop":
            if u.get("tacho_start"):
                elapsed = (datetime.now() - u["tacho_start"]).total_seconds() / 3600
                u["tacho_daily"] = u.get("tacho_daily", 0) + elapsed
                u["tacho_weekly"] = u.get("tacho_weekly", 0) + elapsed
                u["tacho_start"] = None
                h_e, m_e = divmod(int(elapsed * 60), 60)
                dur_str = f"{h_e}h{m_e:02d}m"
                daily = u["tacho_daily"]
                txt = (f"*Остановка*\n\nЗа сессию: *{dur_str}*\nДень итого: *{daily:.1f} ч*" if l=="ru"
                       else f"*Stop*\n\nSession: *{dur_str}*\nDay total: *{daily:.1f}h*" if l=="en"
                       else f"*Arrêt*\n\nSession: *{dur_str}*\nJournée: *{daily:.1f}h*")
                await q.edit_message_text(txt, reply_markup=kb_tacho(uid), parse_mode="Markdown")
            else:
                await q.edit_message_text(t["tacho_not_started"], reply_markup=kb_tacho(uid), parse_mode="Markdown")
        elif action == "status":
            await q.edit_message_text(tacho_status(u, l), reply_markup=kb_tacho(uid), parse_mode="Markdown")
        elif action == "reset":
            u["tacho_start"] = None
            u["tacho_daily"] = 0.0
            u["tacho_weekly"] = 0.0
            reset_txt = "Тахограф сброшен." if l=="ru" else "Tachograph reset." if l=="en" else "Tachygraphe réinitialisé."
            await q.edit_message_text(reset_txt, reply_markup=kb_tacho(uid), parse_mode="Markdown")

    elif d.startswith("w_"):
        weight = float(d[2:])
        u["weight"] = weight
        await q.edit_message_text(t["searching"], parse_mode="Markdown")
        lon1, lat1, _, cc1 = await geocode(u.get("from",""))
        lon2, lat2, _, cc2 = await geocode(u.get("to",""))
        if not (lon1 and lon2):
            await q.edit_message_text(t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        km, dur, rtype = await smart_route(lon1, lat1, lon2, lat2, weight)
        if not km:
            await q.edit_message_text(t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        weather_data = await get_weather(lat2, lon2)
        w_alert = weather_alert(weather_data, l)
        cost, _ = build_cost(km, cc1 or "FR", cc2 or "FR", weight, l, rtype)
        cost = cost.replace("{DUR}", str(dur))
        city_f = u.get("from","").title()
        city_t = u.get("to","").title()
        result = f"*{city_f} — {city_t}*\n\n{cost}{w_alert}"
        await q.edit_message_text(result, reply_markup=kb_after(uid), parse_mode="Markdown")

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
        parkings = await find_tir_parkings(lat, lon, radius_km=60)
        if not parkings:
            await update.message.reply_text(t["no_parking"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        lines = []
        for i, p in enumerate(parkings[:5], 1):
            lines.append(f"*{i}.* {format_parking(p, lat, lon, l)}")
        await update.message.reply_text(
            "\n\n".join(lines), reply_markup=kb_back(uid),
            parse_mode="Markdown", disable_web_page_preview=True)

    elif step == "currency":
        amount, curr = parse_currency(text)
        if not amount or not curr:
            err = "Формат: 100 CHF или 500 PLN" if l=="ru" else "Format: 100 CHF or 500 PLN" if l=="en" else "Format: 100 CHF ou 500 PLN"
            await update.message.reply_text(err, reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        result = convert_currency(amount, curr, l)
        title = f"*{amount} {curr}:*\n\n" if curr != "EUR" else f"*{amount} EUR:*\n\n"
        await update.message.reply_text(title + result, reply_markup=kb_back(uid), parse_mode="Markdown")

    else:
        u["step"] = ""
        await update.message.reply_text(t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")

async def location_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u   = ud(uid); l = u["lang"]; t = T[l]
    loc = update.message.location
    if u.get("step") == "parking":
        await update.message.reply_text(t["search_parking"], parse_mode="Markdown")
        parkings = await find_tir_parkings(loc.latitude, loc.longitude, radius_km=60)
        if not parkings:
            await update.message.reply_text(t["no_parking"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        lines = []
        for i, p in enumerate(parkings[:5], 1):
            lines.append(f"*{i}.* {format_parking(p, loc.latitude, loc.longitude, l)}")
        await update.message.reply_text(
            "\n\n".join(lines), reply_markup=kb_back(uid),
            parse_mode="Markdown", disable_web_page_preview=True)
    else:
        weather_data = await get_weather(loc.latitude, loc.longitude)
        if weather_data:
            cur = weather_data.get("current", {})
            temp = cur.get("temperature_2m","?")
            wind = round(cur.get("wind_speed_10m", 0))
            alert = weather_alert(weather_data, l)
            txt = (f"*Погода в твоей точке:*\n\nТемпература: *{temp}°C*\nВетер: *{wind} км/ч*{alert}" if l=="ru"
                   else f"*Weather at your location:*\n\nTemperature: *{temp}°C*\nWind: *{wind} km/h*{alert}" if l=="en"
                   else f"*Météo à ta position:*\n\nTempérature: *{temp}°C*\nVent: *{wind} km/h*{alert}")
            await update.message.reply_text(txt, reply_markup=kb_back(uid), parse_mode="Markdown")

async def photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = ud(uid); l = u["lang"]; t = T[l]
    if u.get("step") != "cmr":
        await update.message.reply_text(t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")
        return
    await update.message.reply_text(t["ocr_proc"], parse_mode="Markdown")
    photo   = update.message.photo[-1]
    f_obj   = await ctx.bot.get_file(photo.file_id)
    bio     = await f_obj.download_as_bytearray()
    ocr_txt = await do_ocr(bytes(bio))
    if not ocr_txt:
        await update.message.reply_text(t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
        return
    address = extract_address(ocr_txt)
    if address:
        u["to"] = address; u["step"] = "weight"
        await update.message.reply_text(
            f"*{t['addr_found']}:*\n`{address}`\n\n{t['ask_w']}",
            reply_markup=kb_weight(uid), parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"*{t['cmr_raw']}:*\n_{ocr_txt[:400]}_\n\n{t['addr_none']}",
            reply_markup=kb_back(uid), parse_mode="Markdown")

# ─── ЗАПУСК ───────────────────────────────────────────────────────────────────
def main():
    if not TOKEN:
        logger.error("BOT_TOKEN не задан!")
        return
    logger.info(f"ORS-HGV:  {'OK' if ORS_KEY else 'OSRM fallback'}")
    logger.info(f"OCR:      {'OK' if OCR_KEY else 'disabled'}")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("fuel",       cmd_fuel))
    app.add_handler(CommandHandler("rules",      cmd_rules))
    app.add_handler(CommandHandler("route",      cmd_route))
    app.add_handler(CommandHandler("parking",    cmd_parking))
    app.add_handler(CommandHandler("tacho",      cmd_tacho))
    app.add_handler(CommandHandler("bans",       cmd_bans))
    app.add_handler(CommandHandler("emergency",  cmd_emergency))
    app.add_handler(CommandHandler("currency",   cmd_currency))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.PHOTO,    photo_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("GidTrack Bot v6 PRO запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
