import os, logging, aiohttp, re, base64
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

CNAMES = {
    "ru":{"BG":"Болгария","UA":"Украина","RO":"Румыния","PL":"Польша","SK":"Словакия","LU":"Люксембург"},
    "uk":{"BG":"Болгарія","UA":"Україна","RO":"Румунія","PL":"Польща","SK":"Словаччина","LU":"Люксембург"},
    "fr":{"BG":"Bulgarie","UA":"Ukraine","RO":"Roumanie","PL":"Pologne","SK":"Slovaquie","LU":"Luxembourg"},
    "en":{"BG":"Bulgaria","UA":"Ukraine","RO":"Romania","PL":"Poland","SK":"Slovakia","LU":"Luxembourg"},
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
        udata[uid] = {"lang":"ru","step":"","from":"","to":"","weight":20.0}
    return udata[uid]

T = {
"ru":{
    "welcome":"Привет! Я *GidTrack* — умный помощник дальнобойщика в Европе!\n\nПрокладываю грузовые маршруты, считаю топливо, дороги и границы.\n\nВыбери язык:",
    "menu":"Главное меню GidTrack",
    "r_route":"Маршрут LKW + стоимость","r_fuel":"Цены на дизель",
    "r_border":"Документы на границу","r_rules":"Правила ЕС (тахограф)",
    "r_company":"Найти фирму/адрес","r_cmr":"Скан CMR документа",
    "r_lang":"Язык / Language","r_pro":"Pro подписка","r_back":"Назад",
    "ask_from":"Откуда едешь?\n\nНапиши город отправления:\n_Примеры: Lyon, Berlin, Besancon, Warsaw_",
    "ask_to":"Куда едешь?\n\nНапиши город назначения:",
    "ask_w":"Полный вес грузовика (брутто):",
    "w1":"до 7.5т","w2":"7.5—12т","w3":"12—20т","w4":"20—40т",
    "searching":"Прокладываю грузовой маршрут...",
    "not_found":"Город не найден. Проверь название и попробуй ещё раз.\n\nПример: *Lyon*, *Milano*, *Berlin*",
    "ask_co":"Напиши название фирмы и город:\n_Пример: Lidl Lyon или Renault Besancon_",
    "search_co":"Ищу компанию...",
    "ask_cmr":"Отправь фото CMR накладной.\nЯ прочитаю адрес выгрузки и построю маршрут.",
    "ocr_proc":"Читаю документ...",
    "ocr_nokey":"OCR недоступен.\n\nДобавь переменную *OCR_KEY* в Railway → Variables.\nПолучи бесплатно на ocr.space",
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
        "*Время вождения:*\n"
        "• День: до 9 ч (2× в нед. можно 10 ч)\n"
        "• Неделя: до 56 ч\n• 2 недели: до 90 ч\n\n"
        "*Отдых:*\n• После 4.5 ч — 45 мин перерыв\n"
        "• Ежедневный — 11 ч (3× в нед. можно 9 ч)\n"
        "• Еженедельный — 45 ч\n\n"
        "*Запреты движения:*\n"
        "Франция: Пт 22:00—Сб 22:00\nГермания: Вс 00:00—22:00 + праздники\n"
        "Италия: Сб 14:00—Вс 22:00\nШвейцария: Сб 15:00—Вс 23:00\n"
        "Австрия: Вс 00:00—22:00\nБельгия: Сб 22:00—Вс 22:00"
    ),
    "b_ask":"Выбери страну для проверки документов:",
    "pro_text":(
        "*GidTrack Pro — 7€/месяц*\n\n"
        "Бесплатно:\n• 3 маршрута в месяц\n• Цены на дизель\n• Правила ЕС\n\n"
        "Pro:\n• Неограниченные маршруты\n• Скан CMR → адрес → маршрут\n"
        "• Поиск фирм и адресов\n• Документы для 15+ стран\n"
        "• Уведомления о запретах\n• Поддержка 24/7\n\n"
        "Оформить: @gidtrack_support"
    ),
    "help_text":(
        "*GidTrack — команды:*\n\n"
        "/start — главное меню\n/help — эта справка\n"
        "/route — быстрый маршрут\n/fuel — цены на дизель\n/rules — правила ЕС\n\n"
        "Просто напиши город — я начну маршрут!"
    ),
    "lbl_hgv":"Грузовой маршрут (ORS-HGV)","lbl_std":"Стандартный маршрут (OSRM)",
    "lbl_dist":"Расстояние","lbl_time":"Время","lbl_weight":"Вес","lbl_cons":"Расход",
    "lbl_fuel":"Топливо","lbl_toll":"Платные дороги","lbl_vign":"Виньетка CH",
    "lbl_total":"ИТОГО","lbl_tip":"Совет: заправься в","lbl_save":"экономия",
    "new_route":"Новый маршрут","addr_found":"Адрес из CMR","addr_none":"Адрес не определён. Введи вручную.",
    "cmr_raw":"Текст из CMR",
},
"uk":{
    "welcome":"Привіт! Я *GidTrack* — розумний помічник далекобійника!\n\nПрокладаю вантажні маршрути, рахую пальне і дороги по всій Європі.\n\nОбери мову:",
    "menu":"Головне меню GidTrack",
    "r_route":"Маршрут LKW + вартість","r_fuel":"Ціни на дизель",
    "r_border":"Документи на кордон","r_rules":"Правила ЄС (тахограф)",
    "r_company":"Знайти фірму/адресу","r_cmr":"Скан CMR документу",
    "r_lang":"Мова / Language","r_pro":"Pro підписка","r_back":"Назад",
    "ask_from":"Звідки їдеш?\n\nНапиши місто відправлення:\n_Приклади: Lyon, Berlin, Besancon_",
    "ask_to":"Куди їдеш?\n\nНапиши місто призначення:",
    "ask_w":"Повна вага вантажівки (брутто):",
    "w1":"до 7.5т","w2":"7.5—12т","w3":"12—20т","w4":"20—40т",
    "searching":"Прокладаю вантажний маршрут...",
    "not_found":"Місто не знайдено. Перевір назву і спробуй ще раз.",
    "ask_co":"Напиши назву фірми і місто:\n_Приклад: Lidl Lyon або Renault Besancon_",
    "search_co":"Шукаю компанію...",
    "ask_cmr":"Відправ фото CMR. Я прочитаю адресу вивантаження і побудую маршрут.",
    "ocr_proc":"Читаю документ...","ocr_nokey":"OCR недоступний. Додай *OCR_KEY* у Railway.",
    "fuel_prices":(
        "*Ціни на дизель по Європі*\n\n"
        "Найдешевші:\nУкраїна — 0.95€/л\nБолгарія — 1.32€/л\nРумунія — 1.38€/л\n"
        "Польща — 1.41€/л\nСловаччина — 1.48€/л\n\n"
        "Середні:\nФранція — 1.65€/л\nАвстрія — 1.68€/л\nНімеччина — 1.71€/л\n\n"
        "Дорогі:\nШвейцарія — 1.89€/л\nIталія — 1.95€/л\nНідерланди — 2.05€/л"
    ),
    "rules_text":(
        "*Правила ЄС (Рег. 561/2006)*\n\n"
        "День: до 9г (2×/тиж до 10г)\nТиждень: до 56г\n2 тижні: до 90г\n\n"
        "Після 4.5г — 45хв\nЩодобовий: 11г\nЩотижневий: 45г\n\n"
        "*Заборони:*\nФранція: Пт 22:00—Сб 22:00\nНімеччина: Нд+свята\n"
        "Iталія: Сб 14:00—Нд 22:00\nШвейцарія: Сб 15:00—Нд 23:00"
    ),
    "b_ask":"Обери країну для перевірки документів:",
    "pro_text":"*GidTrack Pro — 7€/місяць*\n\nНеобмежені маршрути, скан CMR, підтримка 24/7\n\nОформити: @gidtrack_support",
    "help_text":"*GidTrack — команди:*\n\n/start — головне меню\n/help — довідка\n/route — маршрут\n/fuel — ціни дизелю",
    "lbl_hgv":"Вантажний маршрут (ORS-HGV)","lbl_std":"Стандартний маршрут (OSRM)",
    "lbl_dist":"Відстань","lbl_time":"Час","lbl_weight":"Вага","lbl_cons":"Витрата",
    "lbl_fuel":"Пальне","lbl_toll":"Платні дороги","lbl_vign":"Víньєтка CH",
    "lbl_total":"РАЗОМ","lbl_tip":"Порада: заправся в","lbl_save":"економія",
    "new_route":"Новий маршрут","addr_found":"Адреса з CMR","addr_none":"Адресу не знайдено. Введи вручну.",
    "cmr_raw":"Текст з CMR",
},
"fr":{
    "welcome":"Bonjour! Je suis *GidTrack* — ton assistant chauffeur en Europe!\n\nJe calcule les itinéraires poids lourds, carburant et péages.\n\nChoisis ta langue:",
    "menu":"Menu principal GidTrack",
    "r_route":"Itinéraire PL + coût","r_fuel":"Prix diesel",
    "r_border":"Documents frontière","r_rules":"Règles UE (tachygraphe)",
    "r_company":"Trouver une entreprise","r_cmr":"Scanner CMR",
    "r_lang":"Langue / Language","r_pro":"Abonnement Pro","r_back":"Retour",
    "ask_from":"Ville de départ?\n\nEcris la ville:\n_Exemples: Lyon, Berlin, Besancon_",
    "ask_to":"Ville d'arrivée?\n\nEcris la destination:",
    "ask_w":"Poids total du camion (PTC):",
    "w1":"7.5t","w2":"7.5—12t","w3":"12—20t","w4":"20—40t",
    "searching":"Calcul itinéraire poids lourd...",
    "not_found":"Ville non trouvée. Vérifie le nom et réessaie.",
    "ask_co":"Nom de l'entreprise et ville:\n_Exemple: Lidl Lyon ou Renault Besancon_",
    "search_co":"Recherche en cours...",
    "ask_cmr":"Envoie une photo de la CMR. Je lirai l'adresse de livraison.",
    "ocr_proc":"Lecture du document...","ocr_nokey":"OCR indisponible. Ajoute *OCR_KEY* dans Railway.",
    "fuel_prices":(
        "*Prix diesel en Europe*\n\n"
        "Pas cher:\nUkraine 0.95€/l\nBulgarie 1.32€/l\nRoumanie 1.38€/l\n"
        "Pologne 1.41€/l\nSlovaquie 1.48€/l\n\n"
        "Moyens:\nFrance 1.65€/l\nAutriche 1.68€/l\nAllemagne 1.71€/l\n\n"
        "Chers:\nSuisse 1.89€/l\nItalie 1.95€/l\nPays-Bas 2.05€/l"
    ),
    "rules_text":(
        "*Règles UE (Rèf. 561/2006)*\n\n"
        "Jour: max 9h (2×/sem 10h)\nSemaine: max 56h\n2 sem.: max 90h\n\n"
        "Pause après 4.5h: 45 min\nRepos quotidien: 11h\nHebdomadaire: 45h\n\n"
        "*Interdictions:*\nFrance: Ven 22h—Sam 22h\nAllemagne: Dim+fériés\n"
        "Italie: Sam 14h—Dim 22h\nSuisse: Sam 15h—Dim 23h"
    ),
    "b_ask":"Choisis le pays pour les documents:",
    "pro_text":"*GidTrack Pro — 7€/mois*\n\nItinéraires illimités, scan CMR, support 24/7\n\nAbonnement: @gidtrack_support",
    "help_text":"*GidTrack commandes:*\n\n/start — menu\n/help — aide\n/route — itinéraire\n/fuel — prix diesel",
    "lbl_hgv":"Itinéraire PL (ORS-HGV)","lbl_std":"Itinéraire standard (OSRM)",
    "lbl_dist":"Distance","lbl_time":"Durée","lbl_weight":"Poids","lbl_cons":"Conso",
    "lbl_fuel":"Carburant","lbl_toll":"Péages","lbl_vign":"Vignette CH",
    "lbl_total":"TOTAL","lbl_tip":"Conseil: fais le plein en","lbl_save":"économie",
    "new_route":"Nouvel itinéraire","addr_found":"Adresse CMR","addr_none":"Adresse non trouvée. Saisis manuellement.",
    "cmr_raw":"Texte CMR",
},
"en":{
    "welcome":"Hi! I'm *GidTrack* — your smart HGV driver assistant in Europe!\n\nI calculate truck routes, fuel costs and tolls.\n\nChoose language:",
    "menu":"GidTrack Main Menu",
    "r_route":"HGV Route + cost","r_fuel":"Diesel prices",
    "r_border":"Border documents","r_rules":"EU rules (tachograph)",
    "r_company":"Find company/address","r_cmr":"Scan CMR document",
    "r_lang":"Language / Язык","r_pro":"Pro subscription","r_back":"Back",
    "ask_from":"Where are you departing from?\n\nType the city:\n_Examples: Lyon, Berlin, Besancon_",
    "ask_to":"Where are you going?\n\nType destination city:",
    "ask_w":"Total truck weight (GVW):",
    "w1":"7.5t","w2":"7.5—12t","w3":"12—20t","w4":"20—40t",
    "searching":"Calculating HGV route...",
    "not_found":"City not found. Check the name and try again.",
    "ask_co":"Company name and city:\n_Example: Lidl Lyon or Renault Besancon_",
    "search_co":"Searching...",
    "ask_cmr":"Send a CMR photo. I'll read the delivery address.",
    "ocr_proc":"Reading document...","ocr_nokey":"OCR unavailable. Add *OCR_KEY* to Railway.",
    "fuel_prices":(
        "*Diesel prices in Europe*\n\n"
        "Cheapest:\nUkraine 0.95€/l\nBulgaria 1.32€/l\nRomania 1.38€/l\n"
        "Poland 1.41€/l\nSlovakia 1.48€/l\n\n"
        "Average:\nFrance 1.65€/l\nAustria 1.68€/l\nGermany 1.71€/l\n\n"
        "Expensive:\nSwitzerland 1.89€/l\nItaly 1.95€/l\nNetherlands 2.05€/l"
    ),
    "rules_text":(
        "*EU Rules (Reg. 561/2006)*\n\n"
        "Day: max 9h (2×/week 10h)\nWeek: max 56h\n2 weeks: max 90h\n\n"
        "Break after 4.5h: 45 min\nDaily rest: 11h\nWeekly: 45h\n\n"
        "*Driving bans:*\nFrance: Fri 22:00—Sat 22:00\nGermany: Sun+holidays\n"
        "Italy: Sat 14:00—Sun 22:00\nSwitzerland: Sat 15:00—Sun 23:00"
    ),
    "b_ask":"Choose country for document check:",
    "pro_text":"*GidTrack Pro — €7/month*\n\nUnlimited routes, CMR scan, 24/7 support\n\nSubscribe: @gidtrack_support",
    "help_text":"*GidTrack commands:*\n\n/start — main menu\n/help — help\n/route — route\n/fuel — diesel prices",
    "lbl_hgv":"HGV route (ORS-HGV)","lbl_std":"Standard route (OSRM)",
    "lbl_dist":"Distance","lbl_time":"Time","lbl_weight":"Weight","lbl_cons":"Consumption",
    "lbl_fuel":"Fuel","lbl_toll":"Tolls","lbl_vign":"CH Vignette",
    "lbl_total":"TOTAL","lbl_tip":"Tip: fill up in","lbl_save":"save",
    "new_route":"New route","addr_found":"Address from CMR","addr_none":"Address not found. Enter manually.",
    "cmr_raw":"CMR text",
},
}

BORDER = {
"CH":{
    "ru":"*ШВЕЙЦАРИЯ — ДОКУМЕНТЫ*\n\n• CMR накладная\n• Права CE + карточка водителя\n• Техпаспорт + Зелёная карта\n• Виньетка 40 CHF (обязательно!)\n• Разрешение ЕКМТ\n\nГруз: декларация T1/T2 (таможня!)\n\nВАЖНО: Швейцария не в ЕС — таможня!\nЗапрет: ночь 22:00—05:00, воскресенье",
    "uk":"*ШВЕЙЦАРІЯ — ДОКУМЕНТИ*\n\n• CMR\n• Права CE + картка\n• Техпаспорт + Зелена картка\n• Víньєтка 40 CHF!\n• Дозвіл ЄКМТ\n\nВантаж: декларація T1/T2 (митниця!)\n\nМитниця обов'язкова! Заборона: ніч, неділя",
    "fr":"*SUISSE — DOCUMENTS*\n\n• CMR\n• Permis CE + carte conducteur\n• Carte grise + Carte Verte\n• Vignette 40 CHF (obligatoire!)\n• Autorisation CEMT\n\nMarchandise: déclaration T1/T2 (douane!)\n\nDouane obligatoire! Interdiction: nuit, dimanche",
    "en":"*SWITZERLAND — DOCUMENTS*\n\n• CMR note\n• CE license + driver card\n• Registration + Green Card\n• Vignette 40 CHF (mandatory!)\n• ECMT permit\n\nCargo: T1/T2 declaration (customs!)\n\nCustoms required! Ban: night, Sunday",
},
"DE":{
    "ru":"*ГЕРМАНИЯ — ДОКУМЕНТЫ*\n\n• CMR накладная\n• Права CE + карточка водителя\n• Техпаспорт + Зелёная карта\n• Maut toll-collect.de (обязателен для 7.5т+!)\n\nЗапрет: Вс 00:00—22:00 + праздники\nEuro 4+ в зонах LEZ",
    "uk":"*НIМЕЧЧИНА — ДОКУМЕНТИ*\n\n• CMR\n• Права CE + картка\n• Техпаспорт + Зелена картка\n• Maut toll-collect.de (7.5т+!)\n\nЗаборона: нд 00:00—22:00 + свята\nEuro 4 у зонах LEZ",
    "fr":"*ALLEMAGNE — DOCUMENTS*\n\n• CMR\n• Permis CE + carte conducteur\n• Carte grise + Carte Verte\n• Maut toll-collect.de (obligatoire 7.5t+!)\n\nInterdiction: dim 00h—22h + fériés\nEuro 4 en zones LEZ",
    "en":"*GERMANY — DOCUMENTS*\n\n• CMR note\n• CE license + driver card\n• Registration + Green Card\n• Maut toll-collect.de (mandatory 7.5t+!)\n\nBan: Sun 00:00—22:00 + holidays\nEuro 4 in LEZ zones",
},
"IT":{
    "ru":"*ИТАЛИЯ — ДОКУМЕНТЫ*\n\n• CMR накладная\n• Права CE + карточка водителя\n• Техпаспорт + Зелёная карта\n• Autostrada — платные дороги\n\nЗапреты: Сб 14:00—22:00, Вс 07:00—22:00\nЗоны ZTL в городах — штрафы без предупреждения!",
    "uk":"*IТАЛІЯ — ДОКУМЕНТИ*\n\n• CMR\n• Права CE + картка\n• Техпаспорт + Зелена картка\n• Autostrada платна\n\nЗаборона: Сб 14:00—22:00, Нд 07:00—22:00\nЗони ZTL — штрафи!",
    "fr":"*ITALIE — DOCUMENTS*\n\n• CMR\n• Permis CE + carte conducteur\n• Carte grise + Carte Verte\n• Autostrade payantes\n\nInterdiction: Sam 14h—22h, Dim 07h—22h\nZones ZTL — amendes!",
    "en":"*ITALY — DOCUMENTS*\n\n• CMR note\n• CE license + driver card\n• Registration + Green Card\n• Autostrade toll roads\n\nBan: Sat 14:00—22:00, Sun 07:00—22:00\nZTL zones — fines!",
},
"FR":{
    "ru":"*ФРАНЦИЯ — ДОКУМЕНТЫ*\n\n• CMR накладная\n• Права CE + карточка водителя\n• Техпаспорт + Зелёная карта\n• Péage — платные дороги\n• Crit'Air виньетка (городские зоны)\n\nЗапрет: Пт 22:00—Сб 22:00",
    "uk":"*ФРАНЦІЯ — ДОКУМЕНТИ*\n\n• CMR\n• Права CE + картка\n• Техпаспорт + Зелена картка\n• Péage платний\n• Crit'Air у містах\n\nЗаборона: Пт 22:00—Сб 22:00",
    "fr":"*FRANCE — DOCUMENTS*\n\n• CMR\n• Permis CE + carte conducteur\n• Carte grise + Carte Verte\n• Péages\n• Vignette Crit'Air en ville\n\nInterdiction: Ven 22h—Sam 22h",
    "en":"*FRANCE — DOCUMENTS*\n\n• CMR note\n• CE license + driver card\n• Registration + Green Card\n• Péage toll roads\n• Crit'Air vignette in cities\n\nBan: Fri 22:00—Sat 22:00",
},
"AT":{
    "ru":"*АВСТРИЯ — ДОКУМЕНТЫ*\n\n• CMR накладная\n• Права CE + карточка водителя\n• Техпаспорт + Зелёная карта\n• Maut go-maut.at (для 3.5т+)\n• ЕКМТ или двустороннее\n\nЗапрет: Вс 00:00—22:00\nНочное ограничение скорости 80 км/ч",
    "uk":"*АВСТРІЯ — ДОКУМЕНТИ*\n\n• CMR\n• Права CE + картка\n• Техпаспорт + Зелена картка\n• Maut go-maut.at (3.5т+)\n\nЗаборона: нд 00:00—22:00",
    "fr":"*AUTRICHE — DOCUMENTS*\n\n• CMR\n• Permis CE + carte conducteur\n• Carte grise + Carte Verte\n• Maut go-maut.at (3.5t+)\n\nInterdiction: dim 00h—22h",
    "en":"*AUSTRIA — DOCUMENTS*\n\n• CMR note\n• CE license + driver card\n• Registration + Green Card\n• Maut go-maut.at (3.5t+)\n\nBan: Sun 00:00—22:00",
},
"PL":{
    "ru":"*ПОЛЬША — ДОКУМЕНТЫ*\n\n• CMR накладная\n• Права CE + карточка водителя\n• Техпаспорт + Зелёная карта\n• e-TOLL обязателен (etoll.gov.pl)!\n\nЗапрет: некоторые дороги Пт 18:00—Вс 22:00\nВнимание: viaTOLL отменён, только e-TOLL!",
    "uk":"*ПОЛЬЩА — ДОКУМЕНТИ*\n\n• CMR\n• Права CE + картка\n• Техпаспорт + Зелена картка\n• e-TOLL (etoll.gov.pl) — обов'язково!\n\nЗаборона: Пт 18:00—Нд 22:00 (деякі дороги)",
    "fr":"*POLOGNE — DOCUMENTS*\n\n• CMR\n• Permis CE + carte conducteur\n• Carte grise + Carte Verte\n• e-TOLL (etoll.gov.pl) — obligatoire!\n\nInterdiction: Ven 18h—Dim 22h (certaines routes)",
    "en":"*POLAND — DOCUMENTS*\n\n• CMR note\n• CE license + driver card\n• Registration + Green Card\n• e-TOLL (etoll.gov.pl) — mandatory!\n\nBan: Fri 18:00—Sun 22:00 (some roads)",
},
}

async def geocode(city):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q":city,"format":"json","limit":1,"addressdetails":1},
                headers={"User-Agent":"GidTrackBot/5.0 contact@gidtrack.eu"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                data = await r.json()
                if data:
                    d  = data[0]
                    cc = d.get("address",{}).get("country_code","").upper()
                    return float(d["lon"]), float(d["lat"]), d["display_name"], cc
    except Exception as e:
        logger.error(f"geocode: {e}")
    return None, None, None, None

async def get_route_ors(lon1, lat1, lon2, lat2, weight_t):
    if not ORS_KEY:
        return None, None
    try:
        payload = {
            "coordinates":[[lon1,lat1],[lon2,lat2]],
            "units":"km",
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
                    seg  = data["routes"][0]["summary"]
                    km   = round(seg["distance"])
                    h, m = divmod(round(seg["duration"]/60), 60)
                    return km, f"{h}h{m:02d}" if m else f"{h}h"
                logger.error(f"ORS {r.status}: {(await r.text())[:100]}")
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
                    rt   = data["routes"][0]
                    km   = round(rt["distance"]/1000)
                    h, m = divmod(round(rt["duration"]/60), 60)
                    return km, f"{h}h{m:02d}" if m else f"{h}h"
    except Exception as e:
        logger.error(f"OSRM: {e}")
    return None, None

async def smart_route(lon1, lat1, lon2, lat2, weight_t):
    if ORS_KEY:
        km, dur = await get_route_ors(lon1, lat1, lon2, lat2, weight_t)
        if km:
            return km, dur, "HGV"
    km, dur = await get_route_osrm(lon1, lat1, lon2, lat2)
    if km:
        return km, dur, "STD"
    return None, None, None

async def find_company(query):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q":query,"format":"json","limit":3,"addressdetails":1},
                headers={"User-Agent":"GidTrackBot/5.0 contact@gidtrack.eu"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                return await r.json()
    except Exception as e:
        logger.error(f"company: {e}")
    return []

async def do_ocr(photo_bytes):
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

def build_cost(km, cc1, cc2, weight, lang, rtype="STD"):
    t    = T[lang]
    cons = get_cons(weight)
    fp1  = DIESEL.get(cc1, 1.65)
    fp2  = DIESEL.get(cc2, 1.65)
    fp   = round((fp1+fp2)/2, 2)
    fl   = round(km * cons / 100)
    fc   = round(fl * fp)
    if cc1 == "CH" or cc2 == "CH":
        toll, tlbl = CH_VIGNETTE, t["lbl_vign"]
    else:
        toll = round(km * max(TOLL.get(cc1,10), TOLL.get(cc2,10)) / 100)
        tlbl = t["lbl_toll"]
    total = fc + toll
    cheapest = min(DIESEL, key=DIESEL.get)
    saving   = round(fl * (fp - DIESEL[cheapest]))
    cname    = CNAMES.get(lang, CNAMES["en"]).get(cheapest, cheapest)
    rlbl     = t["lbl_hgv"] if rtype=="HGV" else t["lbl_std"]
    unit     = "km" if lang in ("fr","en") else "км"
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

def kb_after(uid):
    t = T[ud(uid)["lang"]]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["new_route"], callback_data="m_route")],
        [InlineKeyboardButton(t["r_border"],  callback_data="m_border"),
         InlineKeyboardButton(t["r_fuel"],    callback_data="m_fuel")],
        [InlineKeyboardButton(t["r_back"],    callback_data="back")],
    ])

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud(uid)["step"] = ""
    await update.message.reply_text(
        T["ru"]["welcome"], reply_markup=kb_lang(), parse_mode="Markdown")

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        T[ud(uid)["lang"]]["help_text"],
        reply_markup=kb_back(uid), parse_mode="Markdown")

async def cmd_fuel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        T[ud(uid)["lang"]]["fuel_prices"],
        reply_markup=kb_back(uid), parse_mode="Markdown")

async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        T[ud(uid)["lang"]]["rules_text"],
        reply_markup=kb_back(uid), parse_mode="Markdown")

async def cmd_route(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud(uid)["step"] = "from"
    await update.message.reply_text(
        T[ud(uid)["lang"]]["ask_from"],
        reply_markup=kb_back(uid), parse_mode="Markdown")

async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u   = ud(uid); l = u["lang"]; t = T[l]
    d   = q.data

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

    elif d.startswith("b_"):
        cc  = d[2:]
        doc = BORDER.get(cc,{}).get(l) or BORDER.get(cc,{}).get("ru","Not found")
        await q.edit_message_text(doc, reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d == "m_route":
        u["step"] = "from"
        await q.edit_message_text(t["ask_from"], reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d == "m_company":
        u["step"] = "company"
        await q.edit_message_text(t["ask_co"], reply_markup=kb_back(uid), parse_mode="Markdown")

    elif d == "m_cmr":
        if not OCR_KEY:
            await q.edit_message_text(t["ocr_nokey"], reply_markup=kb_back(uid), parse_mode="Markdown")
        else:
            u["step"] = "cmr"
            await q.edit_message_text(t["ask_cmr"], reply_markup=kb_back(uid), parse_mode="Markdown")

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
        cost, _ = build_cost(km, cc1 or "FR", cc2 or "FR", weight, l, rtype)
        cost = cost.replace("{DUR}", str(dur))
        city_f = u.get("from","").title()
        city_t = u.get("to","").title()
        await q.edit_message_text(
            f"*{city_f} — {city_t}*\n\n{cost}",
            reply_markup=kb_after(uid), parse_mode="Markdown")

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

    elif step == "company":
        await update.message.reply_text(t["search_co"], parse_mode="Markdown")
        results = await find_company(text)
        if not results:
            await update.message.reply_text(t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        lines = []
        for i, r in enumerate(results[:3], 1):
            name = r.get("display_name","")[:90]
            lat, lon = r.get("lat"), r.get("lon")
            lines.append(f"*{i}.* {name}\nhttps://maps.google.com/?q={lat},{lon}")
        await update.message.reply_text(
            "\n\n".join(lines), reply_markup=kb_back(uid),
            parse_mode="Markdown", disable_web_page_preview=True)

    else:
        u["step"] = ""
        await update.message.reply_text(t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")

async def photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u   = ud(uid); l = u["lang"]; t = T[l]
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

def main():
    if not TOKEN:
        logger.error("BOT_TOKEN не задан!")
        return
    logger.info(f"ORS-HGV: {'OK' if ORS_KEY else 'нет ключа — OSRM'}")
    logger.info(f"OCR:     {'OK' if OCR_KEY else 'нет ключа'}")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("fuel",   cmd_fuel))
    app.add_handler(CommandHandler("rules",  cmd_rules))
    app.add_handler(CommandHandler("route",  cmd_route))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    logger.info("GidTrack Bot v5 запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
