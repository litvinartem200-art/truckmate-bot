import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")

# Conversation states
CHOOSING_LANG, MAIN_MENU, ROUTE_FROM, ROUTE_TO, ROUTE_WEIGHT, BORDER_COUNTRY = range(6)

TEXTS = {
    "uk": {
        "welcome": "👋 Вітаю в *GidTrack Bot*!\n\nТвій помічник далекобійника в Європі 🚛\n\nОбери мову:",
        "menu_title": "🚛 *Головне меню*\n\nЩо хочеш зробити?",
        "route": "🗺️ Маршрут і вартість",
        "fuel": "⛽ Ціни на пальне",
        "border": "🛂 Документи на кордон",
        "parking": "🅿️ Стоянки TIR",
        "rules": "📋 Правила ЄС",
        "back": "◀️ Назад",
        "language": "🌍 Змінити мову",
        "route_ask_from": "📍 Звідки їдеш?\n\nНапиши місто відправлення.\nПриклад: *Lyon*",
        "route_ask_to": "📍 Куди їдеш?\n\nНапиши місто призначення.\nПриклад: *Munich*",
        "route_ask_weight": "⚖️ Яка повна вага вантажівки?\n\nВибери:",
        "w1": "до 7.5т",
        "w2": "7.5 — 12т",
        "w3": "12 — 40т",
        "calculating": "⏳ Рахую маршрут...",
        "fuel_title": "⛽ *Ціни на дизель сьогодні*\n\n🟢 Найдешевші:\n🇧🇬 Болгарія — 1.32€/л\n🇵🇱 Польща — 1.41€/л\n🇸🇰 Словаччина — 1.48€/л\n\n🟡 Середні:\n🇫🇷 Франція — 1.65€/л\n🇩🇪 Німеччина — 1.71€/л\n🇦🇹 Австрія — 1.68€/л\n\n🔴 Найдорожчі:\n🇨🇭 Швейцарія — 1.89€/л\n🇮🇹 Італія — 1.95€/л\n🇳🇱 Нідерланди — 2.05€/л\n\n_Оновлено сьогодні о 08:00_",
        "border_ask": "🛂 *Документи для перетину кордону*\n\nОбери країну призначення:",
        "parking_info": "🅿️ *Стоянки для TIR*\n\nВідправ своє місцезнаходження 📍\nабо напиши місто — я знайду найближчі стоянки.\n\nПриклад: *Lyon* або *Milano*",
        "rules_text": "📋 *Правила водія ЄС (рег. 561/2006)*\n\n*Час водіння:*\n• День: макс. *9 годин* (2×/тиж до 10г)\n• Тиждень: макс. *56 годин*\n• 2 тижні: макс. *90 годин*\n\n*Обов'язковий відпочинок:*\n• Після 4.5г — *45 хвилин*\n• Щодобовий — *11 годин*\n• Щотижневий — *45 годин*\n\n*Заборони руху:*\n🇫🇷 Пт 22:00 — Сб 22:00\n🇩🇪 Неділя + свята\n🇮🇹 Сб 14:00 — Нд 22:00\n🇨🇭 Сб 15:00 — Нд 23:00",
        "subscribe": "💎 *Підписка GidTrack Pro*\n\n🆓 Безкоштовно:\n• Ціни на пальне\n• 3 маршрути/місяць\n• Правила ЄС\n\n⭐ *Pro — 7€/місяць:*\n• Необмежені маршрути\n• Скан CMR документів\n• Стоянки та рейтинги\n• Сповіщення про заборони\n• Пріоритетна підтримка\n\nДля оформлення: @gidtrack_support",
    },
    "ru": {
        "welcome": "👋 Добро пожаловать в *GidTrack Bot*!\n\nТвой помощник дальнобойщика в Европе 🚛\n\nВыбери язык:",
        "menu_title": "🚛 *Главное меню*\n\nЧто хочешь сделать?",
        "route": "🗺️ Маршрут и стоимость",
        "fuel": "⛽ Цены на топливо",
        "border": "🛂 Документы на границу",
        "parking": "🅿️ Стоянки TIR",
        "rules": "📋 Правила ЕС",
        "back": "◀️ Назад",
        "language": "🌍 Сменить язык",
        "route_ask_from": "📍 Откуда едешь?\n\nНапиши город отправления.\nПример: *Lyon*",
        "route_ask_to": "📍 Куда едешь?\n\nНапиши город назначения.\nПример: *Munich*",
        "route_ask_weight": "⚖️ Какой полный вес грузовика?\n\nВыбери:",
        "w1": "до 7.5т",
        "w2": "7.5 — 12т",
        "w3": "12 — 40т",
        "calculating": "⏳ Считаю маршрут...",
        "fuel_title": "⛽ *Цены на дизель сегодня*\n\n🟢 Самые дешёвые:\n🇧🇬 Болгария — 1.32€/л\n🇵🇱 Польша — 1.41€/л\n🇸🇰 Словакия — 1.48€/л\n\n🟡 Средние:\n🇫🇷 Франция — 1.65€/л\n🇩🇪 Германия — 1.71€/л\n🇦🇹 Австрия — 1.68€/л\n\n🔴 Самые дорогие:\n🇨🇭 Швейцария — 1.89€/л\n🇮🇹 Италия — 1.95€/л\n🇳🇱 Нидерланды — 2.05€/л\n\n_Обновлено сегодня в 08:00_",
        "border_ask": "🛂 *Документы для пересечения границы*\n\nВыбери страну назначения:",
        "parking_info": "🅿️ *Стоянки для TIR*\n\nОтправь своё местоположение 📍\nили напиши город — я найду ближайшие стоянки.\n\nПример: *Lyon* или *Milano*",
        "rules_text": "📋 *Правила водителя ЕС (рег. 561/2006)*\n\n*Время вождения:*\n• День: макс. *9 часов* (2×/нед до 10ч)\n• Неделя: макс. *56 часов*\n• 2 недели: макс. *90 часов*\n\n*Обязательный отдых:*\n• После 4.5ч — *45 минут*\n• Ежедневный — *11 часов*\n• Еженедельный — *45 часов*\n\n*Запреты движения:*\n🇫🇷 Пт 22:00 — Сб 22:00\n🇩🇪 Воскресенье + праздники\n🇮🇹 Сб 14:00 — Вс 22:00\n🇨🇭 Сб 15:00 — Вс 23:00",
        "subscribe": "💎 *Подписка GidTrack Pro*\n\n🆓 Бесплатно:\n• Цены на топливо\n• 3 маршрута/месяц\n• Правила ЕС\n\n⭐ *Pro — 7€/месяц:*\n• Неограниченные маршруты\n• Скан CMR документов\n• Стоянки и рейтинги\n• Уведомления о запретах\n• Приоритетная поддержка\n\nДля оформления: @gidtrack_support",
    },
    "fr": {
        "welcome": "👋 Bienvenue sur *GidTrack Bot*!\n\nTon assistant chauffeur en Europe 🚛\n\nChoisis ta langue:",
        "menu_title": "🚛 *Menu principal*\n\nQue veux-tu faire?",
        "route": "🗺️ Itinéraire et coût",
        "fuel": "⛽ Prix du carburant",
        "border": "🛂 Documents frontière",
        "parking": "🅿️ Parkings TIR",
        "rules": "📋 Règles UE",
        "back": "◀️ Retour",
        "language": "🌍 Changer la langue",
        "route_ask_from": "📍 D'où pars-tu?\n\nÉcris la ville de départ.\nExemple: *Lyon*",
        "route_ask_to": "📍 Où vas-tu?\n\nÉcris la ville d'arrivée.\nExemple: *Munich*",
        "route_ask_weight": "⚖️ Quel est le poids total du camion?\n\nChoisis:",
        "w1": "jusqu'à 7.5t",
        "w2": "7.5 — 12t",
        "w3": "12 — 40t",
        "calculating": "⏳ Calcul de l'itinéraire...",
        "fuel_title": "⛽ *Prix du diesel aujourd'hui*\n\n🟢 Les moins chers:\n🇧🇬 Bulgarie — 1.32€/l\n🇵🇱 Pologne — 1.41€/l\n🇸🇰 Slovaquie — 1.48€/l\n\n🟡 Moyens:\n🇫🇷 France — 1.65€/l\n🇩🇪 Allemagne — 1.71€/l\n🇦🇹 Autriche — 1.68€/l\n\n🔴 Les plus chers:\n🇨🇭 Suisse — 1.89€/l\n🇮🇹 Italie — 1.95€/l\n🇳🇱 Pays-Bas — 2.05€/l\n\n_Mis à jour aujourd'hui à 08:00_",
        "border_ask": "🛂 *Documents pour passer la frontière*\n\nChoisis le pays de destination:",
        "parking_info": "🅿️ *Parkings pour TIR*\n\nEnvoie ta position 📍\nou écris une ville — je trouve les parkings proches.\n\nExemple: *Lyon* ou *Milano*",
        "rules_text": "📋 *Règles chauffeur UE (rèf. 561/2006)*\n\n*Temps de conduite:*\n• Jour: max. *9 heures* (2×/sem jusqu'à 10h)\n• Semaine: max. *56 heures*\n• 2 semaines: max. *90 heures*\n\n*Repos obligatoires:*\n• Après 4.5h — *45 minutes*\n• Quotidien — *11 heures*\n• Hebdomadaire — *45 heures*\n\n*Interdictions de circuler:*\n🇫🇷 Ven 22h — Sam 22h\n🇩🇪 Dimanche + jours fériés\n🇮🇹 Sam 14h — Dim 22h\n🇨🇭 Sam 15h — Dim 23h",
        "subscribe": "💎 *Abonnement GidTrack Pro*\n\n🆓 Gratuit:\n• Prix carburant\n• 3 itinéraires/mois\n• Règles UE\n\n⭐ *Pro — 7€/mois:*\n• Itinéraires illimités\n• Scan CMR documents\n• Parkings et avis\n• Alertes interdictions\n• Support prioritaire\n\nPour s'abonner: @gidtrack_support",
    },
    "en": {
        "welcome": "👋 Welcome to *GidTrack Bot*!\n\nYour European truck driver assistant 🚛\n\nChoose your language:",
        "menu_title": "🚛 *Main Menu*\n\nWhat do you want to do?",
        "route": "🗺️ Route & cost calculator",
        "fuel": "⛽ Fuel prices",
        "border": "🛂 Border documents",
        "parking": "🅿️ TIR parkings",
        "rules": "📋 EU driving rules",
        "back": "◀️ Back",
        "language": "🌍 Change language",
        "route_ask_from": "📍 Where are you departing from?\n\nType the departure city.\nExample: *Lyon*",
        "route_ask_to": "📍 Where are you going?\n\nType the destination city.\nExample: *Munich*",
        "route_ask_weight": "⚖️ What is the total truck weight?\n\nChoose:",
        "w1": "up to 7.5t",
        "w2": "7.5 — 12t",
        "w3": "12 — 40t",
        "calculating": "⏳ Calculating route...",
        "fuel_title": "⛽ *Diesel prices today*\n\n🟢 Cheapest:\n🇧🇬 Bulgaria — 1.32€/l\n🇵🇱 Poland — 1.41€/l\n🇸🇰 Slovakia — 1.48€/l\n\n🟡 Average:\n🇫🇷 France — 1.65€/l\n🇩🇪 Germany — 1.71€/l\n🇦🇹 Austria — 1.68€/l\n\n🔴 Most expensive:\n🇨🇭 Switzerland — 1.89€/l\n🇮🇹 Italy — 1.95€/l\n🇳🇱 Netherlands — 2.05€/l\n\n_Updated today at 08:00_",
        "border_ask": "🛂 *Border crossing documents*\n\nChoose the destination country:",
        "parking_info": "🅿️ *TIR Parkings*\n\nSend your location 📍\nor type a city — I'll find nearby parkings.\n\nExample: *Lyon* or *Milano*",
        "rules_text": "📋 *EU Driver Rules (reg. 561/2006)*\n\n*Driving time:*\n• Day: max. *9 hours* (2×/week up to 10h)\n• Week: max. *56 hours*\n• 2 weeks: max. *90 hours*\n\n*Mandatory rest:*\n• After 4.5h — *45 minutes*\n• Daily — *11 hours*\n• Weekly — *45 hours*\n\n*Driving bans:*\n🇫🇷 Fri 22:00 — Sat 22:00\n🇩🇪 Sunday + public holidays\n🇮🇹 Sat 14:00 — Sun 22:00\n🇨🇭 Sat 15:00 — Sun 23:00",
        "subscribe": "💎 *GidTrack Pro Subscription*\n\n🆓 Free:\n• Fuel prices\n• 3 routes/month\n• EU rules\n\n⭐ *Pro — 7€/month:*\n• Unlimited routes\n• CMR document scan\n• Parkings & reviews\n• Ban alerts\n• Priority support\n\nTo subscribe: @gidtrack_support",
    }
}

BORDER_DOCS = {
    "CH": {
        "ru": "🇨🇭 *Швейцария — необходимые документы*\n\n📄 *Обязательно:*\n• CMR накладная\n• Международные права (МВУ)\n• Техпаспорт + карточка водителя\n• Страховка Зелёная карта\n• Виньетка 40 CHF (обязательно!)\n• ЕКМТ разрешение или двустороннее\n\n📄 *Для груза:*\n• Декларация T1 или T2\n• Санитарные сертификаты (если еда)\n• Ветеринарные документы (если животные)\n\n⚠️ *Важно:*\n• Швейцария не в ЕС — нужна таможня\n• Ограничение ночью: 22:00-05:00\n• Запрет в воскресенье",
        "uk": "🇨🇭 *Швейцарія — необхідні документи*\n\n📄 *Обов'язково:*\n• CMR накладна\n• Міжнародні права (МВУ)\n• Техпаспорт + картка водія\n• Страховка Зелена картка\n• Віньєтка 40 CHF (обов'язково!)\n• ЄКМТ дозвіл або двостороннє\n\n📄 *Для вантажу:*\n• Декларація T1 або T2\n• Санітарні сертифікати (якщо їжа)\n\n⚠️ *Важливо:*\n• Швейцарія не в ЄС — потрібна митниця\n• Обмеження вночі: 22:00-05:00\n• Заборона в неділю",
        "fr": "🇨🇭 *Suisse — documents nécessaires*\n\n📄 *Obligatoires:*\n• Lettre de voiture CMR\n• Permis international (Convention)\n• Carte grise + carte conducteur\n• Assurance Carte Verte\n• Vignette 40 CHF (obligatoire!)\n• Autorisation CEMT ou bilatérale\n\n📄 *Pour la marchandise:*\n• Déclaration T1 ou T2\n• Certificats sanitaires (si alimentaire)\n\n⚠️ *Important:*\n• Suisse hors UE — douane obligatoire\n• Restriction la nuit: 22h-05h\n• Interdiction le dimanche",
        "en": "🇨🇭 *Switzerland — required documents*\n\n📄 *Mandatory:*\n• CMR consignment note\n• International driving license\n• Vehicle registration + driver card\n• Green Card insurance\n• Vignette 40 CHF (mandatory!)\n• ECMT permit or bilateral agreement\n\n📄 *For cargo:*\n• T1 or T2 declaration\n• Health certificates (if food)\n\n⚠️ *Important:*\n• Switzerland not in EU — customs required\n• Night restriction: 22:00-05:00\n• Sunday driving ban"
    },
    "DE": {
        "ru": "🇩🇪 *Германия — необходимые документы*\n\n📄 *Обязательно:*\n• CMR накладная\n• Права категории CE\n• Техпаспорт + карточка водителя\n• Страховка Зелёная карта\n• Maut (платная дорога) — регистрация на toll-collect.de\n\n📄 *Для груза:*\n• Декларация EUR1 или T2L (для ЕС)\n\n⚠️ *Важно:*\n• Maut — обязательна для TIR 7.5т+\n• Запрет движения по воскресеньям\n• Euro 4 минимум в городах (зоны)",
        "uk": "🇩🇪 *Німеччина — необхідні документи*\n\n📄 *Обов'язково:*\n• CMR накладна\n• Права категорії CE\n• Техпаспорт + картка водія\n• Страховка Зелена картка\n• Maut — реєстрація на toll-collect.de\n\n⚠️ *Важливо:*\n• Maut обов'язкова для TIR 7.5т+\n• Заборона руху в неділю\n• Euro 4 мінімум у містах",
        "fr": "🇩🇪 *Allemagne — documents nécessaires*\n\n📄 *Obligatoires:*\n• Lettre de voiture CMR\n• Permis catégorie CE\n• Carte grise + carte conducteur\n• Assurance Carte Verte\n• Maut — inscription sur toll-collect.de\n\n⚠️ *Important:*\n• Maut obligatoire pour poids lourds 7.5t+\n• Interdiction de circuler le dimanche\n• Euro 4 minimum en ville",
        "en": "🇩🇪 *Germany — required documents*\n\n📄 *Mandatory:*\n• CMR consignment note\n• CE category driving license\n• Vehicle registration + driver card\n• Green Card insurance\n• Maut — register at toll-collect.de\n\n⚠️ *Important:*\n• Maut mandatory for trucks 7.5t+\n• Sunday driving ban\n• Euro 4 minimum in cities"
    },
    "IT": {
        "ru": "🇮🇹 *Италия — необходимые документы*\n\n📄 *Обязательно:*\n• CMR накладная\n• Права категории CE\n• Техпаспорт + карточка водителя\n• Страховка Зелёная карта\n• Autostrada — платная, принимают карту\n\n⚠️ *Важно:*\n• Запрет по субботам 14:00-22:00\n• Запрет по воскресеньям 07:00-22:00\n• Предпраздничные дни — ограничения\n• Зоны ZTL в городах — штрафы!",
        "uk": "🇮🇹 *Італія — необхідні документи*\n\n📄 *Обов'язково:*\n• CMR накладна\n• Права категорії CE\n• Техпаспорт + картка водія\n• Страховка Зелена картка\n• Autostrada — платна, приймають картку\n\n⚠️ *Важливо:*\n• Заборона в суботу 14:00-22:00\n• Заборона в неділю 07:00-22:00\n• Зони ZTL у містах — штрафи!",
        "fr": "🇮🇹 *Italie — documents nécessaires*\n\n📄 *Obligatoires:*\n• Lettre de voiture CMR\n• Permis catégorie CE\n• Carte grise + carte conducteur\n• Assurance Carte Verte\n• Autostrade — péage, carte acceptée\n\n⚠️ *Important:*\n• Interdiction samedi 14h-22h\n• Interdiction dimanche 07h-22h\n• Zones ZTL en ville — amendes!",
        "en": "🇮🇹 *Italy — required documents*\n\n📄 *Mandatory:*\n• CMR consignment note\n• CE category driving license\n• Vehicle registration + driver card\n• Green Card insurance\n• Autostrade — toll roads, card accepted\n\n⚠️ *Important:*\n• Ban Saturday 14:00-22:00\n• Ban Sunday 07:00-22:00\n• ZTL zones in cities — fines!"
    }
}

ROUTE_DATA = {
    "lyon-munich": {"km": 580, "time": "5h30", "fuel_l": 85, "toll": {"fr": 18, "ch": 0, "de": 12}},
    "paris-berlin": {"km": 1050, "time": "9h00", "fuel_l": 155, "toll": {"fr": 25, "de": 18}},
    "besancon-turin": {"km": 340, "time": "3h45", "fuel_l": 50, "toll": {"ch": 42, "tunnel": 14, "it": 9}},
    "lyon-barcelona": {"km": 650, "time": "6h00", "fuel_l": 95, "toll": {"fr": 45, "es": 22}},
}

user_data_store = {}

def get_lang(user_id):
    return user_data_store.get(user_id, {}).get("lang", "ru")

def t(user_id, key):
    lang = get_lang(user_id)
    return TEXTS.get(lang, TEXTS["ru"]).get(key, key)

def lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk"),
         InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ])

def main_menu_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(user_id, "route"), callback_data="menu_route")],
        [InlineKeyboardButton(t(user_id, "fuel"), callback_data="menu_fuel")],
        [InlineKeyboardButton(t(user_id, "border"), callback_data="menu_border")],
        [InlineKeyboardButton(t(user_id, "parking"), callback_data="menu_parking")],
        [InlineKeyboardButton(t(user_id, "rules"), callback_data="menu_rules")],
        [InlineKeyboardButton("💎 Pro", callback_data="menu_subscribe"),
         InlineKeyboardButton(t(user_id, "language"), callback_data="menu_lang")]
    ])

def back_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(user_id, "back"), callback_data="back_main")]
    ])

def weight_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(user_id, "w1"), callback_data="weight_7"),
         InlineKeyboardButton(t(user_id, "w2"), callback_data="weight_12")],
        [InlineKeyboardButton(t(user_id, "w3"), callback_data="weight_40")],
        [InlineKeyboardButton(t(user_id, "back"), callback_data="back_main")]
    ])

def border_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇨🇭 Швейцария / Suisse", callback_data="border_CH")],
        [InlineKeyboardButton("🇩🇪 Германия / Allemagne", callback_data="border_DE")],
        [InlineKeyboardButton("🇮🇹 Италия / Italie", callback_data="border_IT")],
        [InlineKeyboardButton(t(user_id, "back"), callback_data="back_main")]
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

    elif data == "back_main" or data == "menu_lang":
        if data == "menu_lang":
            await query.edit_message_text(
                t(uid, "welcome"),
                reply_markup=lang_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                t(uid, "menu_title"),
                reply_markup=main_menu_keyboard(uid),
                parse_mode="Markdown"
            )

    elif data == "menu_fuel":
        await query.edit_message_text(
            t(uid, "fuel_title"),
            reply_markup=back_keyboard(uid),
            parse_mode="Markdown"
        )

    elif data == "menu_rules":
        await query.edit_message_text(
            t(uid, "rules_text"),
            reply_markup=back_keyboard(uid),
            parse_mode="Markdown"
        )

    elif data == "menu_parking":
        await query.edit_message_text(
            t(uid, "parking_info"),
            reply_markup=back_keyboard(uid),
            parse_mode="Markdown"
        )

    elif data == "menu_subscribe":
        await query.edit_message_text(
            t(uid, "subscribe"),
            reply_markup=back_keyboard(uid),
            parse_mode="Markdown"
        )

    elif data == "menu_border":
        await query.edit_message_text(
            t(uid, "border_ask"),
            reply_markup=border_keyboard(uid),
            parse_mode="Markdown"
        )

    elif data.startswith("border_"):
        country = data.split("_")[1]
        lang = get_lang(uid)
        doc_text = BORDER_DOCS.get(country, {}).get(lang, "Информация не найдена")
        await query.edit_message_text(
            doc_text,
            reply_markup=back_keyboard(uid),
            parse_mode="Markdown"
        )

    elif data == "menu_route":
        if uid not in user_data_store:
            user_data_store[uid] = {}
        user_data_store[uid]["step"] = "from"
        await query.edit_message_text(
            t(uid, "route_ask_from"),
            reply_markup=back_keyboard(uid),
            parse_mode="Markdown"
        )

    elif data.startswith("weight_"):
        weight = data.split("_")[1]
        if uid not in user_data_store:
            user_data_store[uid] = {}
        user_data_store[uid]["weight"] = weight
        user_data_store[uid]["step"] = "calculating"
        city_from = user_data_store[uid].get("from", "?")
        city_to = user_data_store[uid].get("to", "?")
        fuel_price = 1.65
        route_key = f"{city_from.lower()}-{city_to.lower()}"
        if route_key in ROUTE_DATA:
            r = ROUTE_DATA[route_key]
            fuel_cost = round(r["fuel_l"] * fuel_price)
            toll_total = sum(r["toll"].values())
            total = fuel_cost + toll_total
            toll_str = "\n".join([f"  {k.upper()}: {v}€" for k, v in r["toll"].items()])
            lang = get_lang(uid)
            if lang == "uk":
                result = (f"✅ *Маршрут: {city_from.title()} → {city_to.title()}*\n\n"
                         f"📏 Відстань: {r['km']} км\n"
                         f"⏱️ Час: ~{r['time']}\n\n"
                         f"*Вартість:*\n"
                         f"⛽ Пальне ({r['fuel_l']}л × {fuel_price}€) — {fuel_cost}€\n"
                         f"🛣️ Дороги та збори:\n{toll_str}\n\n"
                         f"━━━━━━━━━━━━\n"
                         f"💰 *Разом: {total}€*\n\n"
                         f"💡 Порада: заправся перед виїздом!")
            elif lang == "fr":
                result = (f"✅ *Itinéraire: {city_from.title()} → {city_to.title()}*\n\n"
                         f"📏 Distance: {r['km']} km\n"
                         f"⏱️ Durée: ~{r['time']}\n\n"
                         f"*Coût:*\n"
                         f"⛽ Carburant ({r['fuel_l']}l × {fuel_price}€) — {fuel_cost}€\n"
                         f"🛣️ Péages et taxes:\n{toll_str}\n\n"
                         f"━━━━━━━━━━━━\n"
                         f"💰 *Total: {total}€*\n\n"
                         f"💡 Conseil: fais le plein avant de partir!")
            elif lang == "en":
                result = (f"✅ *Route: {city_from.title()} → {city_to.title()}*\n\n"
                         f"📏 Distance: {r['km']} km\n"
                         f"⏱️ Time: ~{r['time']}\n\n"
                         f"*Cost:*\n"
                         f"⛽ Fuel ({r['fuel_l']}l × {fuel_price}€) — {fuel_cost}€\n"
                         f"🛣️ Tolls & fees:\n{toll_str}\n\n"
                         f"━━━━━━━━━━━━\n"
                         f"💰 *Total: {total}€*\n\n"
                         f"💡 Tip: fill up before departure!")
            else:
                result = (f"✅ *Маршрут: {city_from.title()} → {city_to.title()}*\n\n"
                         f"📏 Расстояние: {r['km']} км\n"
                         f"⏱️ Время: ~{r['time']}\n\n"
                         f"*Стоимость:*\n"
                         f"⛽ Топливо ({r['fuel_l']}л × {fuel_price}€) — {fuel_cost}€\n"
                         f"🛣️ Дороги и сборы:\n{toll_str}\n\n"
                         f"━━━━━━━━━━━━\n"
                         f"💰 *Итого: {total}€*\n\n"
                         f"💡 Совет: заправься перед выездом!")
        else:
            lang = get_lang(uid)
            if lang == "ru":
                result = (f"🗺️ *Маршрут: {city_from.title()} → {city_to.title()}*\n\n"
                         f"⏳ Этот маршрут добавляем в базу.\n\n"
                         f"Уже доступны готовые расчёты:\n"
                         f"• Lyon → Munich\n• Paris → Berlin\n• Besançon → Turin\n• Lyon → Barcelona\n\n"
                         f"📩 Хочешь добавить этот маршрут? Напиши @gidtrack_support")
            else:
                result = (f"🗺️ *Route: {city_from.title()} → {city_to.title()}*\n\n"
                         f"⏳ This route is being added to our database.\n\n"
                         f"Already available:\n"
                         f"• Lyon → Munich\n• Paris → Berlin\n• Besançon → Turin\n• Lyon → Barcelona")
        await query.edit_message_text(
            result,
            reply_markup=back_keyboard(uid),
            parse_mode="Markdown"
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    step = user_data_store.get(uid, {}).get("step", "")

    if step == "from":
        if uid not in user_data_store:
            user_data_store[uid] = {}
        user_data_store[uid]["from"] = text
        user_data_store[uid]["step"] = "to"
        await update.message.reply_text(
            t(uid, "route_ask_to"),
            reply_markup=back_keyboard(uid),
            parse_mode="Markdown"
        )
    elif step == "to":
        user_data_store[uid]["to"] = text
        user_data_store[uid]["step"] = "weight"
        await update.message.reply_text(
            t(uid, "route_ask_weight"),
            reply_markup=weight_keyboard(uid),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            t(uid, "menu_title"),
            reply_markup=main_menu_keyboard(uid),
            parse_mode="Markdown"
        )

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
