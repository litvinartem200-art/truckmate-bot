import os, logging, aiohttp, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN   = os.environ.get("BOT_TOKEN", "")
OCR_KEY = os.environ.get("OCR_KEY", "")

DIESEL = {
    "FR":1.65,"DE":1.71,"IT":1.95,"CH":1.89,"ES":1.55,"BE":1.68,
    "NL":2.05,"AT":1.68,"PL":1.41,"CZ":1.52,"SK":1.48,"HU":1.44,
    "RO":1.38,"BG":1.32,"UA":0.95,"LU":1.48,"SI":1.55,"HR":1.42,
}

TOLL_PER_100 = {
    "FR":6.5,"IT":8.0,"ES":5.5,"AT":6.0,"PL":2.5,
    "CZ":2.5,"HU":3.5,"BE":2.0,"SI":3.0,"HR":4.0,
    "DE":2.8,"BG":1.5,"RO":1.5,"SK":2.0,
}
CH_VIGNETTE = 42

FLAGS = {
    "BG":"Bulgaria","UA":"Ukraine","RO":"Romania","PL":"Poland",
    "SK":"Slovakia","HU":"Hungary","LU":"Luxembourg","FR":"France",
    "DE":"Germany","ES":"Spain","AT":"Austria","BE":"Belgium",
    "CH":"Switzerland","IT":"Italy","NL":"Netherlands",
}

udata = {}
def ud(uid):
    if uid not in udata: udata[uid] = {"lang":"ru","step":""}
    return udata[uid]

def consumption(w):
    if w<=7.5: return 24.0
    elif w<=12: return 27.0
    elif w<=20: return 30.0
    elif w<=30: return 33.0
    return 36.0

T = {
"ru":{
  "welcome":"Привет! Я *GidTrack* — умный помощник дальнобойщика в Европе! Выбери язык:",
  "menu":"Главное меню GidTrack",
  "r_route":"Маршрут и стоимость","r_fuel":"Цены на дизель",
  "r_border":"Документы на границу","r_rules":"Правила ЕС",
  "r_company":"Найти фирму/адрес","r_cmr":"Скан CMR",
  "r_lang":"Язык","r_pro":"Pro подписка","r_back":"Назад",
  "ask_from":"Откуда едешь? Напиши город:\n_Lyon, Berlin, Paris, Besancon_",
  "ask_to":"Куда едешь? Напиши город назначения:",
  "ask_w":"Полный вес грузовика:","w1":"до 7.5т","w2":"7.5-12т","w3":"12-20т","w4":"20-40т",
  "searching":"Ищу маршрут...",
  "ask_co":"Напиши название фирмы и город:\n_Lidl Lyon, Peugeot Besancon_",
  "search_co":"Ищу компанию...","not_found":"Не найдено. Попробуй ещё раз.",
  "ask_cmr":"Отправь фото CMR — прочитаю адрес выгрузки и построю маршрут.",
  "ocr_proc":"Читаю документ...","ocr_nokey":"OCR недоступен. Нужен OCR_KEY в Railway.",
  "fuel":"Цены дизеля сегодня:\n\n🟢 Дёшево:\n Болгария — 1.32/л\n Польша — 1.41/л\n Словакия — 1.48/л\n\n🟡 Средние:\n Франция — 1.65/л\n Германия — 1.71/л\n Австрия — 1.68/л\n\n🔴 Дорого:\n Швейцария — 1.89/л\n Италия — 1.95/л\n Нидерланды — 2.05/л\n\nЗаправляйся в Польше или Люксембурге — экономия до 60",
  "rules":"Правила ЕС (561/2006)\n\nВождение:\n• День: до 9 часов\n• Неделя: до 56 часов\n• 2 недели: до 90 часов\n\nОтдых:\n• После 4.5ч - 45 минут\n• Ежедневный - 11 часов\n• Еженедельный - 45 часов\n\nЗапреты:\nФранция: Пт 22:00 - Сб 22:00\nГермания: Воскресенье и праздники\nИталия: Сб 14:00 - Вс 22:00\nШвейцария: Сб 15:00 - Вс 23:00",
  "b_ask":"Выбери страну:",
  "pro":"GidTrack Pro — 7/месяц\n\nБесплатно: 3 маршрута, топливо, правила\nPro: все маршруты, скан CMR, стоянки TIR, алерты\n\nОформить: @gidtrack_support",
},
"uk":{
  "welcome":"Привіт! Я *GidTrack* — помічник далекобійника! Обери мову:",
  "menu":"Головне меню GidTrack",
  "r_route":"Маршрут і вартість","r_fuel":"Ціни на дизель",
  "r_border":"Документи на кордон","r_rules":"Правила ЄС",
  "r_company":"Знайти фірму/адресу","r_cmr":"Скан CMR",
  "r_lang":"Мова","r_pro":"Pro підписка","r_back":"Назад",
  "ask_from":"Звідки їдеш? Напиши місто:\n_Lyon, Berlin, Paris, Besancon_",
  "ask_to":"Куди їдеш? Напиши місто призначення:",
  "ask_w":"Повна вага вантажівки:","w1":"до 7.5т","w2":"7.5-12т","w3":"12-20т","w4":"20-40т",
  "searching":"Шукаю маршрут...",
  "ask_co":"Напиши назву фірми і місто:\n_Lidl Lyon, Renault Besancon_",
  "search_co":"Шукаю компанію...","not_found":"Не знайдено. Спробуй ще раз.",
  "ask_cmr":"Відправ фото CMR — прочитаю адресу вивантаження і побудую маршрут.",
  "ocr_proc":"Читаю документ...","ocr_nokey":"OCR недоступний. Потрібен OCR_KEY.",
  "fuel":"Ціни дизелю сьогодні:\n\nДешево: Болгарія 1.32, Польща 1.41\nСередні: Франція 1.65, Німеччина 1.71\nДорого: Швейцарія 1.89, Італія 1.95",
  "rules":"Правила ЄС: день до 9г, тиждень до 56г, 2 тижні до 90г. Відпочинок після 4.5г - 45хв, щодобовий 11г.",
  "b_ask":"Обери країну:",
  "pro":"GidTrack Pro — 7/місяць\n\nОформити: @gidtrack_support",
},
"fr":{
  "welcome":"Bonjour! Je suis *GidTrack* — ton assistant chauffeur! Choisis ta langue:",
  "menu":"Menu principal GidTrack",
  "r_route":"Itinéraire et coût","r_fuel":"Prix carburant",
  "r_border":"Documents frontière","r_rules":"Règles UE",
  "r_company":"Trouver entreprise","r_cmr":"Scanner CMR",
  "r_lang":"Langue","r_pro":"Abonnement Pro","r_back":"Retour",
  "ask_from":"D'où pars-tu? Ecris la ville:\n_Lyon, Berlin, Paris_",
  "ask_to":"Où vas-tu? Ecris la ville d'arrivée:",
  "ask_w":"Poids total du camion:","w1":"jusqu'a 7.5t","w2":"7.5-12t","w3":"12-20t","w4":"20-40t",
  "searching":"Calcul de l'itineraire...",
  "ask_co":"Ecris le nom et la ville:\n_Lidl Lyon, Peugeot Besancon_",
  "search_co":"Recherche...","not_found":"Non trouve. Reessaie.",
  "ask_cmr":"Envoie une photo CMR — je lirai l'adresse de livraison.",
  "ocr_proc":"Lecture du document...","ocr_nokey":"OCR indisponible. Ajoute OCR_KEY.",
  "fuel":"Prix diesel aujourd'hui:\n\nPas cher: Bulgarie 1.32, Pologne 1.41\nMoyens: France 1.65, Allemagne 1.71\nCher: Suisse 1.89, Italie 1.95",
  "rules":"Regles UE: jour max 9h, semaine max 56h. Pause apres 4.5h - 45min.",
  "b_ask":"Choisis le pays:",
  "pro":"GidTrack Pro — 7/mois. Itineraires illimites, scan CMR.\n\n@gidtrack_support",
},
"en":{
  "welcome":"Hi! I'm *GidTrack* — your truck driver assistant! Choose language:",
  "menu":"GidTrack Main Menu",
  "r_route":"Route & cost","r_fuel":"Fuel prices",
  "r_border":"Border documents","r_rules":"EU rules",
  "r_company":"Find company","r_cmr":"Scan CMR",
  "r_lang":"Language","r_pro":"Pro subscription","r_back":"Back",
  "ask_from":"Where are you departing? Type city:\n_Lyon, Berlin, Paris_",
  "ask_to":"Where are you going? Type destination:",
  "ask_w":"Total truck weight:","w1":"up to 7.5t","w2":"7.5-12t","w3":"12-20t","w4":"20-40t",
  "searching":"Calculating route...",
  "ask_co":"Type company name and city:\n_Lidl Lyon, Renault Paris_",
  "search_co":"Searching...","not_found":"Not found. Try again.",
  "ask_cmr":"Send a CMR photo — I'll read the delivery address.",
  "ocr_proc":"Reading document...","ocr_nokey":"OCR unavailable. Add OCR_KEY.",
  "fuel":"Diesel prices today:\n\nCheap: Bulgaria 1.32, Poland 1.41\nAverage: France 1.65, Germany 1.71\nExpensive: Switzerland 1.89, Italy 1.95",
  "rules":"EU rules: day max 9h, week max 56h. Break after 4.5h - 45min.",
  "b_ask":"Choose country:",
  "pro":"GidTrack Pro — 7/month. Unlimited routes, CMR scan.\n\n@gidtrack_support",
},
}

BORDER_DOCS = {
"CH":{"ru":"ШВЕЙЦАРИЯ - ДОКУМЕНТЫ\n\nОбязательно:\n CMR накладная\n Права CE + карточка\n Техпаспорт\n Зелёная карта\n Виньетка 40 CHF\n Разрешение ЕКМТ\n\nГруз: декларация T1/T2\n\nВАЖНО: Швейцария - не ЕС! Нужна таможня.\nЗапрет ночью 22:00-05:00\nЗапрет по воскресеньям",
      "uk":"ШВЕЙЦАРІЯ - ДОКУМЕНТИ\n\nObov'yazkovo:\n CMR накладна\n Права CE + картка\n Техпаспорт\n Зелена картка\n Віньєтка 40 CHF\n Дозвіл ЄКМТ\n\nВАЖЛИВО: Митниця обов'язкова!",
      "fr":"SUISSE - DOCUMENTS\n\nObligatoires:\n CMR\n Permis CE + carte\n Carte grise\n Carte Verte\n Vignette 40 CHF\n Autorisation CEMT\n\nIMPORTANT: Hors UE - douane obligatoire!",
      "en":"SWITZERLAND - DOCUMENTS\n\nMandatory:\n CMR note\n CE license + card\n Registration\n Green Card\n Vignette 40 CHF\n ECMT permit\n\nIMPORTANT: Not EU - customs required!"},
"DE":{"ru":"ГЕРМАНИЯ - ДОКУМЕНТЫ\n\nОбязательно:\n CMR накладная\n Права CE + карточка\n Техпаспорт + Зелёная карта\n Maut (toll-collect.de)\n\nMaut обязателен для 7.5т+\nЗапрет по воскресеньям\nEuro 4+ в городах",
      "uk":"НIМЕЧЧИНА - ДОКУМЕНТИ\n\nMaut (toll-collect.de) обов'язковий для 7.5т+\nЗаборона в неділю",
      "fr":"ALLEMAGNE - DOCUMENTS\n\nMaut (toll-collect.de) obligatoire 7.5t+\nInterdiction dimanche",
      "en":"GERMANY - DOCUMENTS\n\nMaut (toll-collect.de) mandatory 7.5t+\nSunday ban"},
"IT":{"ru":"ИТАЛИЯ - ДОКУМЕНТЫ\n\nОбязательно:\n CMR накладная\n Права CE + карточка\n Техпаспорт + Зелёная карта\n Autostrada платная\n\nЗапрет Сб 14:00-22:00\nЗапрет Вс 07:00-22:00\nЗоны ZTL в городах - штрафы!",
      "uk":"IТАЛІЯ - ДОКУМЕНТИ\n\nЗаборона Сб 14:00-22:00\nЗаборона Нд 07:00-22:00\nЗони ZTL - штрафи!",
      "fr":"ITALIE - DOCUMENTS\n\nInterdiction Sam 14h-22h\nInterdiction Dim 07h-22h\nZones ZTL - amendes!",
      "en":"ITALY - DOCUMENTS\n\nBan Sat 14:00-22:00\nBan Sun 07:00-22:00\nZTL zones - fines!"},
"FR":{"ru":"ФРАНЦИЯ - ДОКУМЕНТЫ\n\nОбязательно:\n CMR накладная\n Права CE + карточка\n Техпаспорт + Зелёная карта\n Crit'Air виньетка (в городах)\n\nЗапрет Пт 22:00 - Сб 22:00\nПеаж - автоматические кассы",
      "uk":"ФРАНЦІЯ - ДОКУМЕНТИ\n\nCrit'Air обов'язковий у містах\nЗаборона Пт 22:00 - Сб 22:00",
      "fr":"FRANCE - DOCUMENTS\n\nVignette Crit'Air obligatoire\nInterdiction Ven 22h - Sam 22h",
      "en":"FRANCE - DOCUMENTS\n\nCrit'Air vignette required in cities\nBan Fri 22:00 - Sat 22:00"},
}

async def geocode(city):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": city, "format": "json", "limit": 1, "addressdetails": 1}
        headers = {"User-Agent": "GidTrackBot/3.0 gidtrack@proton.me"}
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
                if data:
                    d = data[0]
                    cc = d.get("address", {}).get("country_code", "").upper()
                    return float(d["lon"]), float(d["lat"]), d["display_name"], cc
    except Exception as e:
        logger.error(f"geocode: {e}")
    return None, None, None, None

async def osrm(lon1, lat1, lon2, lat2):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params={"overview":"false"}, timeout=aiohttp.ClientTimeout(total=15)) as r:
                data = await r.json()
                if data.get("code") == "Ok":
                    rt = data["routes"][0]
                    km = round(rt["distance"]/1000)
                    h, m = divmod(round(rt["duration"]/60), 60)
                    return km, f"{h}h{m:02d}" if m else f"{h}h"
    except Exception as e:
        logger.error(f"osrm: {e}")
    return None, None

async def find_company(query):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "limit": 3, "addressdetails": 1}
        headers = {"User-Agent": "GidTrackBot/3.0 gidtrack@proton.me"}
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
                return await r.json()
    except Exception as e:
        logger.error(f"company: {e}")
    return []

async def do_ocr(photo_bytes):
    if not OCR_KEY: return None
    try:
        import base64
        b64 = base64.b64encode(photo_bytes).decode()
        async with aiohttp.ClientSession() as s:
            async with s.post("https://api.ocr.space/parse/image",
                data={"base64Image": f"data:image/jpeg;base64,{b64}",
                      "apikey": OCR_KEY, "language": "eng",
                      "isOverlayRequired": False},
                timeout=aiohttp.ClientTimeout(total=30)) as r:
                res = await r.json()
                if res.get("IsErroredOnProcessing"): return None
                pr = res.get("ParsedResults", [])
                if pr: return pr[0].get("ParsedText", "")
    except Exception as e:
        logger.error(f"ocr: {e}")
    return None

def find_addr(text):
    for line in [l.strip() for l in text.split("\n") if l.strip()]:
        if any(k in line.lower() for k in ["street","rue","str","via","avenue","allee","road","ul.","platz"]):
            if len(line) > 8: return line
    for line in [l.strip() for l in text.split("\n") if l.strip()]:
        if re.search(r'\d{4,5}', line) and len(line) > 8: return line
    return None

def build_cost(km, cc1, cc2, weight, lang):
    c = consumption(weight)
    fp1 = DIESEL.get(cc1, 1.65)
    fp2 = DIESEL.get(cc2, 1.65)
    fp  = round((fp1 + fp2) / 2, 2)
    fl  = round(km * c / 100)
    fc  = round(fl * fp)
    ch  = CH_VIGNETTE if cc1=="CH" or cc2=="CH" else 0
    tc  = 0 if ch else round(km * max(TOLL_PER_100.get(cc1,0), TOLL_PER_100.get(cc2,0)) / 100)
    total = fc + ch + tc
    cheapest_cc = min(DIESEL, key=DIESEL.get)
    saving = round(fl * (fp - DIESEL[cheapest_cc]))
    cheap_name = FLAGS.get(cheapest_cc, cheapest_cc)
    if lang=="fr":
        out = [f"Carburant: {fl}l x {fp}= *{fc}*"]
        if ch: out.append(f"Vignette CH: *{ch}*")
        if tc: out.append(f"Peages: *{tc}*")
        out.append(f"TOTAL: *{total}*")
        if saving>5: out.append(f"Conseil: fais le plein en {cheap_name} - economie ~{saving}")
    elif lang=="en":
        out = [f"Fuel: {fl}l x {fp}= *{fc}*"]
        if ch: out.append(f"CH vignette: *{ch}*")
        if tc: out.append(f"Tolls: *{tc}*")
        out.append(f"TOTAL: *{total}*")
        if saving>5: out.append(f"Tip: fill up in {cheap_name} - save ~{saving}")
    elif lang=="uk":
        out = [f"Пальне: {fl}л x {fp}= *{fc}*"]
        if ch: out.append(f"Віньєтка CH: *{ch}*")
        if tc: out.append(f"Дороги/збори: *{tc}*")
        out.append(f"РАЗОМ: *{total}*")
        if saving>5: out.append(f"Порада: заправся в {cheap_name} - економія ~{saving}")
    else:
        out = [f"Топливо: {fl}л x {fp}= *{fc}*"]
        if ch: out.append(f"Виньетка CH: *{ch}*")
        if tc: out.append(f"Дороги/сборы: *{tc}*")
        out.append(f"ИТОГО: *{total}*")
        if saving>5: out.append(f"Совет: заправься в {cheap_name} - экономия ~{saving}")
    return "\n".join(out)

def kb_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Украинский", callback_data="lang_uk"),
         InlineKeyboardButton("Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("Francais", callback_data="lang_fr"),
         InlineKeyboardButton("English", callback_data="lang_en")],
    ])

def kb_menu(uid):
    l=ud(uid)["lang"]; t=T[l]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["r_route"], callback_data="m_route")],
        [InlineKeyboardButton(t["r_fuel"],  callback_data="m_fuel"),
         InlineKeyboardButton(t["r_rules"], callback_data="m_rules")],
        [InlineKeyboardButton(t["r_border"],callback_data="m_border")],
        [InlineKeyboardButton(t["r_company"],callback_data="m_company"),
         InlineKeyboardButton(t["r_cmr"],   callback_data="m_cmr")],
        [InlineKeyboardButton(t["r_pro"],   callback_data="m_pro"),
         InlineKeyboardButton(t["r_lang"],  callback_data="m_lang")],
    ])

def kb_w(uid):
    l=ud(uid)["lang"]; t=T[l]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["w1"],callback_data="w_7.5"),
         InlineKeyboardButton(t["w2"],callback_data="w_12")],
        [InlineKeyboardButton(t["w3"],callback_data="w_20"),
         InlineKeyboardButton(t["w4"],callback_data="w_40")],
        [InlineKeyboardButton(t["r_back"],callback_data="back")],
    ])

def kb_border(uid):
    l=ud(uid)["lang"]; t=T[l]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Швейцария / Suisse",   callback_data="b_CH")],
        [InlineKeyboardButton("Германия / Allemagne", callback_data="b_DE")],
        [InlineKeyboardButton("Италия / Italie",      callback_data="b_IT")],
        [InlineKeyboardButton("Франция / France",     callback_data="b_FR")],
        [InlineKeyboardButton(t["r_back"],             callback_data="back")],
    ])

def kb_back(uid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(T[ud(uid)["lang"]]["r_back"],callback_data="back")]])

def kb_new_route(uid):
    l=ud(uid)["lang"]; t=T[l]
    lbl = "Новый маршрут" if l=="ru" else "Новий маршрут" if l=="uk" else "Nouvel itin." if l=="fr" else "New route"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbl, callback_data="m_route")],
        [InlineKeyboardButton(t["r_back"], callback_data="back")],
    ])

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud(uid)["step"] = ""
    await update.message.reply_text(T["ru"]["welcome"], reply_markup=kb_lang(), parse_mode="Markdown")

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; u = ud(uid); l = u["lang"]; t = T[l]
    d = q.data

    if d.startswith("lang_"):
        u["lang"] = d[5:]; l = u["lang"]; t = T[l]; u["step"] = ""
        await q.edit_message_text(t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")
    elif d in ("back","m_lang"):
        u["step"] = ""
        if d=="m_lang":
            await q.edit_message_text(t["welcome"], reply_markup=kb_lang(), parse_mode="Markdown")
        else:
            await q.edit_message_text(t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")
    elif d=="m_fuel":
        await q.edit_message_text(t["fuel"], reply_markup=kb_back(uid), parse_mode="Markdown")
    elif d=="m_rules":
        await q.edit_message_text(t["rules"], reply_markup=kb_back(uid), parse_mode="Markdown")
    elif d=="m_pro":
        await q.edit_message_text(t["pro"], reply_markup=kb_back(uid), parse_mode="Markdown")
    elif d=="m_border":
        await q.edit_message_text(t["b_ask"], reply_markup=kb_border(uid), parse_mode="Markdown")
    elif d.startswith("b_"):
        cc = d[2:]
        doc = BORDER_DOCS.get(cc,{}).get(l) or BORDER_DOCS.get(cc,{}).get("ru","Информация не найдена")
        await q.edit_message_text(doc, reply_markup=kb_back(uid), parse_mode="Markdown")
    elif d=="m_route":
        u["step"]="from"
        await q.edit_message_text(t["ask_from"], reply_markup=kb_back(uid), parse_mode="Markdown")
    elif d=="m_company":
        u["step"]="company"
        await q.edit_message_text(t["ask_co"], reply_markup=kb_back(uid), parse_mode="Markdown")
    elif d=="m_cmr":
        if not OCR_KEY:
            await q.edit_message_text(t["ocr_nokey"], reply_markup=kb_back(uid), parse_mode="Markdown")
        else:
            u["step"]="cmr"
            await q.edit_message_text(t["ask_cmr"], reply_markup=kb_back(uid), parse_mode="Markdown")
    elif d.startswith("w_"):
        weight = float(d[2:])
        u["weight"] = weight
        await q.edit_message_text(t["searching"], parse_mode="Markdown")
        lon1,lat1,_,cc1 = await geocode(u.get("from",""))
        lon2,lat2,_,cc2 = await geocode(u.get("to",""))
        if not (lon1 and lon2):
            await q.edit_message_text(t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        km, dur = await osrm(lon1,lat1,lon2,lat2)
        if not km:
            await q.edit_message_text(t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        cost = build_cost(km, cc1 or "FR", cc2 or "FR", weight, l)
        city_f = u.get("from","").title()
        city_t = u.get("to","").title()
        lbl_km = "Расстояние" if l=="ru" else "Відстань" if l=="uk" else "Distance"
        lbl_t  = "Время" if l=="ru" else "Час" if l=="uk" else "Temps" if l=="fr" else "Time"
        lbl_w  = "Вес" if l=="ru" else "Вага" if l=="uk" else "Poids" if l=="fr" else "Weight"
        text = (f"{city_f} to {city_t}\n\n"
                f"{lbl_km}: *{km} km*\n"
                f"{lbl_t}: *{dur}*\n"
                f"{lbl_w}: *{weight}t* | Conso: *{consumption(weight)}l/100*\n\n"
                f"{cost}")
        await q.edit_message_text(text, reply_markup=kb_new_route(uid), parse_mode="Markdown")

async def message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    u = ud(uid); l = u["lang"]; t = T[l]
    step = u.get("step","")

    if step=="from":
        u["from"]=text; u["step"]="to"
        await update.message.reply_text(t["ask_to"], reply_markup=kb_back(uid), parse_mode="Markdown")
    elif step=="to":
        u["to"]=text; u["step"]="weight"
        await update.message.reply_text(t["ask_w"], reply_markup=kb_w(uid), parse_mode="Markdown")
    elif step=="company":
        await update.message.reply_text(t["search_co"], parse_mode="Markdown")
        results = await find_company(text)
        if not results:
            await update.message.reply_text(t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
            return
        lines = []
        for i,r in enumerate(results[:3],1):
            addr = r.get("display_name","")[:90]
            lat,lon = r.get("lat",""),r.get("lon","")
            maps = f"https://maps.google.com/?q={lat},{lon}"
            lines.append(f"*{i}.* {addr}\nMaps: {maps}")
        await update.message.reply_text("\n\n".join(lines), reply_markup=kb_back(uid),
            parse_mode="Markdown", disable_web_page_preview=True)
    else:
        u["step"]=""
        await update.message.reply_text(t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")

async def photo_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = ud(uid); l = u["lang"]; t = T[l]
    if u.get("step") != "cmr":
        await update.message.reply_text(t["menu"], reply_markup=kb_menu(uid), parse_mode="Markdown")
        return
    await update.message.reply_text(t["ocr_proc"], parse_mode="Markdown")
    photo = update.message.photo[-1]
    f = await ctx.bot.get_file(photo.file_id)
    bio = await f.download_as_bytearray()
    ocr_text = await do_ocr(bytes(bio))
    if not ocr_text:
        await update.message.reply_text(t["not_found"], reply_markup=kb_back(uid), parse_mode="Markdown")
        return
    address = find_addr(ocr_text)
    if address:
        u["to"]=address; u["step"]="weight"
        found_lbl = "Адрес найден" if l=="ru" else "Адресу знайдено" if l=="uk" else "Adresse trouvee" if l=="fr" else "Address found"
        weight_lbl = "Укажи вес грузовика:" if l=="ru" else "Вкажи вагу:" if l=="uk" else "Indique le poids:" if l=="fr" else "Select truck weight:"
        await update.message.reply_text(
            f"{found_lbl}:\n*{address}*\n\n{weight_lbl}",
            reply_markup=kb_w(uid), parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"Текст из CMR:\n_{ocr_text[:400]}_\n\nАдрес не найден автоматически. Введи вручную.",
            reply_markup=kb_back(uid), parse_mode="Markdown")

def main():
    if not TOKEN:
        logger.error("BOT_TOKEN not set!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.PHOTO, photo_msg))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))
    logger.info("GidTrack Bot v3 started!")
    app.run_polling()

if __name__ == "__main__":
    main()
