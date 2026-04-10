import asyncio
import logging
import os
import time
import base64
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from books import BOOKS, BOOKS_PER_PAGE
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
# ─── ENV ───────────────────────────────────────────────────────────────────────
BOT_TOKEN        = os.environ.get("BOT_TOKEN", "")
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY   = os.environ.get("OPENAI_API_KEY", "")
HF_TOKEN         = os.environ.get("HF_TOKEN", "")
REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL", "@smart_dehqon_channel")
OWM_API_KEY      = os.environ.get("OWM_API_KEY", "")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN sozlanmagan!")
# ─── API URLS ──────────────────────────────────────────────────────────────────
GROQ_URL        = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_TEXT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-8b:generateContent"
GEMINI_VIS_URL  = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
HF_BLIP_URL     = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-base"
GROQ_VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.2-90b-vision-preview",
    "llama-3.2-11b-vision-preview",
]
GROQ_TEXT_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "mixtral-8x7b-32768",
]
# ─── VILOYATLAR ───────────────────────────────────────────────────────────────
REGIONS = {
    "🏙 Toshkent sh.":     {"city": "Tashkent",  "lat": 41.2995, "lon": 69.2401},
    "🌆 Toshkent v.":      {"city": "Chirchiq",  "lat": 41.4694, "lon": 69.5833},
    "🌿 Samarqand":        {"city": "Samarkand", "lat": 39.6542, "lon": 66.9597},
    "🕌 Buxoro":           {"city": "Bukhara",   "lat": 39.7747, "lon": 64.4286},
    "⛰ Namangan":         {"city": "Namangan",  "lat": 41.0011, "lon": 71.6722},
    "🏔 Andijon":          {"city": "Andijan",   "lat": 40.7821, "lon": 72.3442},
    "🌾 Farg'ona":         {"city": "Fergana",   "lat": 40.3842, "lon": 71.7843},
    "🌵 Qashqadaryo":      {"city": "Qarshi",    "lat": 38.8600, "lon": 65.7897},
    "☀️ Surxondaryo":     {"city": "Termez",    "lat": 37.2242, "lon": 67.2783},
    "🌊 Xorazm":           {"city": "Urgench",   "lat": 41.5500, "lon": 60.6333},
    "⛏ Navoiy":           {"city": "Navoi",     "lat": 40.0843, "lon": 65.3791},
    "🌱 Jizzax":           {"city": "Jizzakh",   "lat": 40.1158, "lon": 67.8422},
    "🚜 Sirdaryo":         {"city": "Gulistan",  "lat": 40.4897, "lon": 68.7842},
    "🏜 Qoraqalpog'iston": {"city": "Nukus",     "lat": 42.4533, "lon": 59.6139},
}
WEATHER_ICONS = {
    "01": "☀️", "02": "⛅", "03": "🌥", "04": "☁️",
    "09": "🌧", "10": "🌦", "11": "⛈", "13": "❄️", "50": "🌫",
}
# ─── OB-HAVO ──────────────────────────────────────────────────────────────────
def get_weather_icon(code: str) -> str:
    return WEATHER_ICONS.get(code[:2], "🌡")
def get_weather(lat, lon, city) -> str:
    try:
        return get_weather_owm(lat, lon) if OWM_API_KEY else get_weather_wttr(city)
    except Exception as e:
        logger.error(f"Weather: {e}")
        return "❌ Ob-havo ma'lumotini olishda xatolik."
def get_weather_owm(lat, lon) -> str:
    url = (f"https://api.openweathermap.org/data/2.5/forecast"
           f"?lat={lat}&lon={lon}&appid={OWM_API_KEY}&units=metric&lang=uz&cnt=24")
    data = requests.get(url, timeout=10).json()
    if data.get("cod") != "200":
        raise Exception(data.get("message"))
    cur   = data["list"][0]
    temp  = round(cur["main"]["temp"])
    feels = round(cur["main"]["feels_like"])
    hum   = cur["main"]["humidity"]
    wind  = round(cur["wind"]["speed"] * 3.6)
    desc  = cur["weather"][0]["description"].capitalize()
    icon  = get_weather_icon(cur["weather"][0]["icon"])
    pres  = cur["main"]["pressure"]
    days  = {}
    for item in data["list"]:
        d = item["dt_txt"][:10]
        if d not in days:
            days[d] = {"min": [], "max": [], "desc": "", "icon": ""}
        days[d]["min"].append(item["main"]["temp_min"])
        days[d]["max"].append(item["main"]["temp_max"])
        days[d]["desc"] = item["weather"][0]["description"].capitalize()
        days[d]["icon"] = get_weather_icon(item["weather"][0]["icon"])
    fc = ""
    for i, (date, d) in enumerate(list(days.items())[:4]):
        if i == 0:
            continue
        fc += f"\n{d['icon']} {date}: {round(min(d['min']))}°C ~ {round(max(d['max']))}°C | {d['desc']}"
    return (f"{icon} <b>Hozirgi holat:</b> {desc}\n"
            f"🌡 Harorat: <b>{temp}°C</b> (his: {feels}°C)\n"
            f"💧 Namlik: <b>{hum}%</b>\n💨 Shamol: <b>{wind} km/soat</b>\n"
            f"🔵 Bosim: <b>{pres} hPa</b>\n\n📅 <b>Kelgusi kunlar:</b>{fc}")
def get_weather_wttr(city) -> str:
    r = requests.get(f"https://wttr.in/{city}?format=j1",
                     headers={"User-Agent": "AgroBot/1.0"}, timeout=15)
    r.raise_for_status()
    data  = r.json()
    cur   = data["current_condition"][0]
    desc  = (cur.get("weatherDesc", [{}])[0]).get("value", "")
    fc    = ""
    for i, day in enumerate(data.get("weather", [])):
        if i == 0:
            continue
        desc_d = day["hourly"][4].get("weatherDesc", [{}])[0].get("value", "")
        fc += f"\n☁️ {day['date']}: {day['mintempC']}°C ~ {day['maxtempC']}°C | {desc_d}"
    return (f"☀️ <b>Hozirgi holat:</b> {desc}\n"
            f"🌡 Harorat: <b>{cur['temp_C']}°C</b> (his: {cur['FeelsLikeC']}°C)\n"
            f"💧 Namlik: <b>{cur['humidity']}%</b>\n💨 Shamol: <b>{cur['windspeedKmph']} km/soat</b>\n"
            f"🔵 Bosim: <b>{cur['pressure']} hPa</b>\n\n📅 <b>Kelgusi kunlar:</b>{fc}")
# ─── YORDAMCHI ────────────────────────────────────────────────────────────────
def clean_md(text: str) -> str:
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*',     r'<i>\1</i>', text)
    text = re.sub(r'#{1,6}\s+(.+)', r'<b>\1</b>', text)
    text = re.sub(r'`([^`]+)`',     r'<code>\1</code>', text)
    return text
def split_text(text: str, max_len: int = 3800) -> list:
    if len(text) <= max_len:
        return [text]
    parts = []
    while len(text) > max_len:
        at = text.rfind('\n', 0, max_len)
        if at == -1:
            at = max_len
        parts.append(text[:at])
        text = text[at:].lstrip('\n')
    if text:
        parts.append(text)
    return parts
# ─── AI PROVIDERS ─────────────────────────────────────────────────────────────
def _groq_text(prompt: str) -> str:
    if not GROQ_API_KEY:
        raise Exception("GROQ_API_KEY yo'q")
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    last_err = None
    for model in GROQ_TEXT_MODELS:
        for attempt in range(2):
            try:
                resp = requests.post(
                    GROQ_URL, headers=headers,
                    json={"model": model,
                          "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 2048, "temperature": 0.7},
                    timeout=30,
                )
                if resp.status_code == 429:
                    time.sleep(5 if attempt == 0 else 10)
                    continue
                if resp.status_code == 200:
                    text = resp.json()["choices"][0]["message"]["content"].strip()
                    if text:
                        logger.info(f"✅ Groq text ({model})")
                        return text
                last_err = Exception(f"Groq text {resp.status_code} ({model})")
                break
            except Exception as e:
                last_err = e
                break
    raise last_err or Exception("Groq text barcha urinishlar muvaffaqiyatsiz")
def _groq_vision(prompt: str, image_bytes: bytes) -> str:
    if not GROQ_API_KEY:
        raise Exception("GROQ_API_KEY yo'q")
    headers   = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    last_err  = None
    for model in GROQ_VISION_MODELS:
        for attempt in range(2):
            try:
                resp = requests.post(
                    GROQ_URL, headers=headers,
                    json={"model": model,
                          "messages": [{"role": "user", "content": [
                              {"type": "text", "text": prompt},
                              {"type": "image_url",
                               "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                          ]}],
                          "max_tokens": 2048, "temperature": 0.5},
                    timeout=45,
                )
                if resp.status_code == 429:
                    time.sleep(5 if attempt == 0 else 15)
                    continue
                if resp.status_code == 200:
                    text = resp.json()["choices"][0]["message"]["content"].strip()
                    if text:
                        logger.info(f"✅ Groq vision ({model})")
                        return text
                last_err = Exception(f"Groq vision {resp.status_code} ({model})")
                break
            except Exception as e:
                last_err = e
                break
    raise last_err or Exception("Groq vision barcha modellar muvaffaqiyatsiz")
def _gemini_text(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY yo'q")
    last_err = None
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{GEMINI_TEXT_URL}?key={GEMINI_API_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}},
                timeout=30,
            )
            if resp.status_code == 429:
                time.sleep([10, 20, 30][attempt])
                last_err = Exception("Gemini text 429")
                continue
            if resp.status_code == 200:
                cands = resp.json().get("candidates", [])
                if cands:
                    parts = cands[0].get("content", {}).get("parts", [])
                    text  = parts[0].get("text", "").strip() if parts else ""
                    if text:
                        logger.info("✅ Gemini text")
                        return text
            raise Exception(f"Gemini text {resp.status_code}")
        except Exception as e:
            if "429" not in str(e):
                raise
            last_err = e
    raise last_err or Exception("Gemini text limit tugdi")
def _gemini_vision(prompt: str, image_bytes: bytes) -> str:
    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY yo'q")
    b64     = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 2048},
    }
    last_err = None
    for attempt in range(3):
        try:
            resp = requests.post(f"{GEMINI_VIS_URL}?key={GEMINI_API_KEY}",
                                 json=payload, timeout=45)
            if resp.status_code == 429:
                time.sleep([10, 20, 30][attempt])
                last_err = Exception("Gemini vision 429")
                continue
            if resp.status_code == 200:
                cands = resp.json().get("candidates", [])
                if cands:
                    parts = cands[0].get("content", {}).get("parts", [])
                    text  = parts[0].get("text", "").strip() if parts else ""
                    if text:
                        logger.info("✅ Gemini vision")
                        return text
            raise Exception(f"Gemini vision {resp.status_code}")
        except Exception as e:
            if "429" not in str(e):
                raise
            last_err = e
    raise last_err or Exception("Gemini vision limit tugdi")
def _openai_text(prompt: str) -> str:
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY yo'q")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}",
                 "Content-Type": "application/json"},
        json={"model": "gpt-4o-mini",
              "messages": [{"role": "user", "content": prompt}],
              "max_tokens": 2048, "temperature": 0.7},
        timeout=30,
    )
    if resp.status_code == 429:
        raise Exception("OpenAI kredit tugagan")
    if resp.status_code != 200:
        raise Exception(f"OpenAI {resp.status_code}")
    return resp.json()["choices"][0]["message"]["content"].strip()
def _hf_blip_caption(image_bytes: bytes) -> str:
    if not HF_TOKEN:
        raise Exception("HF_TOKEN yo'q")
    headers = {
        "Authorization":   f"Bearer {HF_TOKEN}",
        "x-wait-for-model": "true",
        "x-use-cache":      "false",
    }
    for attempt in range(3):
        if attempt > 0:
            time.sleep(20)
        try:
            resp = requests.post(HF_BLIP_URL, headers=headers,
                                 data=image_bytes, timeout=60)
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, list) and result:
                    caption = result[0].get("generated_text", "")
                    if caption:
                        return caption
            elif resp.status_code in (503, 504):
                logger.warning(f"HF BLIP {resp.status_code}, retry {attempt + 1}...")
                continue
            raise Exception(f"HF BLIP {resp.status_code}")
        except Exception as e:
            if "503" in str(e) or "504" in str(e):
                continue
            raise
    raise Exception("HF BLIP muvaffaqiyatsiz")
# ─── ASOSIY AI ────────────────────────────────────────────────────────────────
#  Rasm:  Groq Vision → Gemini Vision → HF BLIP + Groq/Gemini text
#  Matn:  Groq → Gemini → OpenAI
async def ask_ai(prompt: str, image_bytes: bytes = None) -> str:
    errors = []
    if image_bytes:
        if GROQ_API_KEY:
            try:
                return await asyncio.to_thread(_groq_vision, prompt, image_bytes)
            except Exception as e:
                logger.warning(f"Groq Vision: {e}")
                errors.append(f"Groq Vision: {e}")
        if GEMINI_API_KEY:
            try:
                return await asyncio.to_thread(_gemini_vision, prompt, image_bytes)
            except Exception as e:
                logger.warning(f"Gemini Vision: {e}")
                errors.append(f"Gemini Vision: {e}")
        if HF_TOKEN:
            try:
                caption = await asyncio.to_thread(_hf_blip_caption, image_bytes)
                detail  = (
                    f"Rasm tavsifi (inglizcha): '{caption}'\n\n"
                    "Sen O'zbekiston qishloq xo'jaligi bo'yicha expert agronommisan. "
                    "Ushbu rasm tavsifiga asoslanib O'zbek tilida batafsil yoz:\n"
                    "1. 🌿 O'simlik turi\n2. 🦠 Kasallik/muammo\n"
                    "3. 💊 Davolash usullari\n4. 🛡 Oldini olish\n5. ⚠️ Tavsiyalar"
                )
                if GROQ_API_KEY:
                    return await asyncio.to_thread(_groq_text, detail)
                elif GEMINI_API_KEY:
                    return await asyncio.to_thread(_gemini_text, detail)
            except Exception as e:
                logger.warning(f"HF BLIP: {e}")
                errors.append(f"HF BLIP: {e}")
        logger.error(f"Rasm AI barchasi ishlamadi: {errors}")
        return ("❌ Rasm tahlili hozirda ishlamayapti.\n\n"
                "Biroz kutib qayta urinib ko'ring. 🙏")
    if GROQ_API_KEY:
        try:
            return await asyncio.to_thread(_groq_text, prompt)
        except Exception as e:
            logger.warning(f"Groq: {e}")
            errors.append(str(e))
    if GEMINI_API_KEY:
        try:
            return await asyncio.to_thread(_gemini_text, prompt)
        except Exception as e:
            logger.warning(f"Gemini: {e}")
            errors.append(str(e))
    if OPENAI_API_KEY:
        try:
            return await asyncio.to_thread(_openai_text, prompt)
        except Exception as e:
            logger.warning(f"OpenAI: {e}")
            errors.append(str(e))
    logger.error(f"Matn AI barchasi ishlamadi: {errors}")
    return ("❌ AI xizmati vaqtincha ishlamayapti.\n\n"
            "Bir necha daqiqadan so'ng qayta urinib ko'ring. 🙏")
# ─── TELEGRAM ─────────────────────────────────────────────────────────────────
async def is_subscribed(user_id: int, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        m = await ctx.bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return m.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except Exception as e:
        logger.warning(f"Sub check: {e}")
        return False
def sub_kb():
    link = (REQUIRED_CHANNEL if REQUIRED_CHANNEL.startswith("http")
            else f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=link)],
        [InlineKeyboardButton("✅ Obunani tekshirish",    callback_data="check_sub")],
    ])
def sub_text():
    return (
        "⚠️ <b>Botdan foydalanish uchun avval kanalga obuna bo'ling!</b>\n\n"
        f"📢 Kanal: {REQUIRED_CHANNEL}\n\n"
        "Obuna bo'lgach ✅ <b>Obunani tekshirish</b> tugmasini bosing."
    )
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌤 Ob-havo",               callback_data="weather_menu")],
        [InlineKeyboardButton("🌱 Ekish tavsiyasi (AI)",  callback_data="ekish_menu")],
        [InlineKeyboardButton("🦠 Kasallik aniqlash (AI)", callback_data="disease_menu")],
        [InlineKeyboardButton("📚 Kitoblar menyusi",      callback_data="books_menu_0")],
    ])
def weather_kb():
    keys = list(REGIONS.keys())
    kb   = []
    for i in range(0, len(keys), 2):
        row = [InlineKeyboardButton(keys[i], callback_data=f"weather_{i}")]
        if i + 1 < len(keys):
            row.append(InlineKeyboardButton(keys[i + 1], callback_data=f"weather_{i + 1}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")])
    return InlineKeyboardMarkup(kb)
def books_kb(page: int):
    if page < 0 or not BOOKS:
        return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]])
    s  = page * BOOKS_PER_PAGE
    e  = min(s + BOOKS_PER_PAGE, len(BOOKS))
    kb = [[InlineKeyboardButton(f"{i + 1}. {BOOKS[i][0][:45]}", url=BOOKS[i][1])] for i in range(s, e)]
    nav = []
    if page > 0:       nav.append(InlineKeyboardButton("◀️ Oldingi", callback_data=f"books_menu_{page - 1}"))
    if e < len(BOOKS): nav.append(InlineKeyboardButton("Keyingi ▶️", callback_data=f"books_menu_{page + 1}"))
    if nav: kb.append(nav)
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")])
    return InlineKeyboardMarkup(kb)
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_subscribed(user.id, ctx):
        await update.message.reply_text(sub_text(), reply_markup=sub_kb(), parse_mode="HTML")
        return
    await update.message.reply_text(
        f"Assalomu alaykum, <b>{user.first_name}</b>! 👋\n\n"
        "🌾 <b>Smart Dehqon Botiga</b> xush kelibsiz!\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🌤 <b>Ob-havo</b> — 14 viloyat uchun real vaqt\n"
        "🌱 <b>Ekish tavsiyasi</b> — AI yordamida professional tavsiya\n"
        "🦠 <b>Kasallik aniqlash</b> — Rasm orqali AI tahlil\n"
        "📚 <b>Kitoblar</b> — 122 ta qishloq xo'jaligi kitobi\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Quyidagi bo'limdan birini tanlang 👇",
        reply_markup=main_kb(), parse_mode="HTML",
    )
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    data = q.data
    uid  = update.effective_user.id
    if data == "check_sub":
        if await is_subscribed(uid, ctx):
            user = update.effective_user
            await q.edit_message_text(
                f"✅ <b>Tabriklaymiz, {user.first_name}!</b>\n\nObuna tasdiqlandi!\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🌤 <b>Ob-havo</b> — 14 viloyat\n"
                "🌱 <b>Ekish tavsiyasi</b> — AI\n"
                "🦠 <b>Kasallik aniqlash</b> — AI\n"
                "📚 <b>Kitoblar</b> — 122 ta\n"
                "━━━━━━━━━━━━━━━━━━━━",
                reply_markup=main_kb(), parse_mode="HTML",
            )
        else:
            await q.answer("❌ Siz hali obuna bo'lmagansiz!", show_alert=True)
        return
    if not await is_subscribed(uid, ctx):
        await q.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
        await q.edit_message_text(sub_text(), reply_markup=sub_kb(), parse_mode="HTML")
        return
    if data == "main_menu":
        await q.edit_message_text(
            "🌾 <b>Smart Dehqon Bot</b> — Asosiy menyu\n\nQuyidagi bo'limdan birini tanlang 👇",
            reply_markup=main_kb(), parse_mode="HTML",
        )
    elif data == "weather_menu":
        await q.edit_message_text(
            "🌤 <b>Ob-havo</b>\n\nViloyatni tanlang 👇",
            reply_markup=weather_kb(), parse_mode="HTML",
        )
    elif data.startswith("weather_") and data[8:].isdigit():
        idx  = int(data[8:])
        keys = list(REGIONS.keys())
        if idx >= len(keys):
            await q.answer("Xatolik!", show_alert=True)
            return
        name = keys[idx]
        info = REGIONS[name]
        await q.edit_message_text(f"⏳ <b>{name}</b> ob-havosi yuklanmoqda...", parse_mode="HTML")
        try:
            wt = get_weather(info["lat"], info["lon"], info["city"])
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Yangilash",    callback_data=data)],
                [InlineKeyboardButton("⬅️ Viloyatlar",  callback_data="weather_menu")],
                [InlineKeyboardButton("🏠 Bosh menyu",  callback_data="main_menu")],
            ])
            await q.edit_message_text(
                f"🌤 <b>{name} ob-havosi</b>\n━━━━━━━━━━━━━━━━━━━━\n{wt}",
                reply_markup=kb, parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Weather: {e}")
            await q.edit_message_text(
                "❌ Ob-havo ma'lumotini olishda xatolik.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Orqaga", callback_data="weather_menu")]]),
            )
    elif data == "ekish_menu":
        ctx.user_data["state"] = "waiting_ekish"
        await q.edit_message_text(
            "🌱 <b>Ekish tavsiyasi (AI)</b>\n\n"
            "Qaysi ekin haqida ma'lumot olmoqchisiz?\n\n"
            "📝 Masalan:\n• <i>G'o'za</i>\n• <i>Bug'doy</i>\n"
            "• <i>Pomidor</i>\n• <i>Kartoshka</i>\n• <i>Sholi</i>\n\n"
            "Ekin nomini yozing 👇",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]),
            parse_mode="HTML",
        )
    elif data == "disease_menu":
        ctx.user_data["state"] = "waiting_disease_photo"
        await q.edit_message_text(
            "🦠 <b>O'simlik kasalligini aniqlash (AI)</b>\n\n"
            "O'simlik yoki bargning <b>aniq, yorug'</b> rasmini yuboring.\n"
            "AI kasallikni aniqlab, davolash usulini tavsiya qiladi.\n\n"
            "📸 <b>Rasmni yuboring</b> 👇",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]),
            parse_mode="HTML",
        )
    elif data.startswith("books_menu_"):
        ps = data.replace("books_menu_", "")
        if not ps.isdigit():
            await q.answer("Xatolik!", show_alert=True)
            return
        page  = int(ps)
        total = (len(BOOKS) - 1) // BOOKS_PER_PAGE + 1 if BOOKS else 1
        s_idx = page * BOOKS_PER_PAGE + 1
        e_idx = min((page + 1) * BOOKS_PER_PAGE, len(BOOKS))
        await q.edit_message_text(
            f"📚 <b>Qishloq xo'jaligi kitoblari</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Sahifa {page + 1}/{total} | {s_idx}–{e_idx}-kitoblar\n\n"
            "Kitob nomiga bosib PDF yuklab olishingiz mumkin 👇",
            reply_markup=books_kb(page), parse_mode="HTML",
        )
async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await is_subscribed(uid, ctx):
        await update.message.reply_text(sub_text(), reply_markup=sub_kb(), parse_mode="HTML")
        return
    state = ctx.user_data.get("state", "")
    if state == "waiting_ekish":
        ctx.user_data["state"] = ""
        ekin = update.message.text.strip()
        msg  = await update.message.reply_text(
            f"⏳ <b>{ekin}</b> uchun AI tavsiya tayyorlanmoqda...\n"
            "Bu bir necha soniya olishi mumkin.",
            parse_mode="HTML",
        )
        prompt = (
            f"Sen O'zbekiston qishloq xo'jaligi bo'yicha professional agronommisan. "
            f"'{ekin}' ekini uchun quyidagilarni O'zbek tilida batafsil va professional tarzda yoz:\n\n"
            f"1. 📅 Ekish vaqti (oylar ko'rsatilsin)\n"
            f"2. 🌱 Tuproq tayyorlash (haydash, o'g'itlash)\n"
            f"3. 💧 Sug'orish rejimi (necha kundan bir, qancha)\n"
            f"4. 🧪 O'g'itlash tavsiyasi (NPK miqdorlari)\n"
            f"5. 🌿 Parvarishlash (o't o'chirish, ishlash)\n"
            f"6. 🌾 Yig'im-terim vaqti\n"
            f"7. 🦠 Asosiy kasalliklar va zararkunandalar\n"
            f"8. ⚠️ Muhim ogohlantirishlar\n\n"
            f"Javob O'zbekiston iqlimi va sharoitiga mos, aniq va amaliy bo'lsin."
        )
        result = clean_md(await ask_ai(prompt))
        header = f"🌱 <b>{ekin.upper()} — Ekish tavsiyasi</b>\n\n"
        parts  = split_text(result)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌱 Boshqa ekin so'rash", callback_data="ekish_menu")],
            [InlineKeyboardButton("🏠 Bosh menu",           callback_data="main_menu")],
        ])
        try:
            await msg.edit_text(
                header + parts[0],
                reply_markup=None if len(parts) > 1 else kb,
                parse_mode="HTML",
            )
            for i in range(1, len(parts)):
                await update.message.reply_text(
                    parts[i],
                    reply_markup=kb if i == len(parts) - 1 else None,
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error(f"Edit error: {e}")
            await msg.delete()
            await update.message.reply_text(
                header + result[:3800], reply_markup=kb, parse_mode="HTML"
            )
    else:
        await update.message.reply_text(
            "📋 Menyu orqali bo'lim tanlang:",
            reply_markup=main_kb(), parse_mode="HTML",
        )
async def photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await is_subscribed(uid, ctx):
        await update.message.reply_text(sub_text(), reply_markup=sub_kb(), parse_mode="HTML")
        return
    state = ctx.user_data.get("state", "")
    if state == "waiting_disease_photo":
        ctx.user_data["state"] = ""
        msg = await update.message.reply_text(
            "🔍 Rasm tahlil qilinmoqda...\nAI o'simlikni ko'rib chiqmoqda, biroz kuting."
        )
        try:
            photo     = update.message.photo[-1]
            file      = await photo.get_file()
            img_bytes = bytes(await file.download_as_bytearray())
            prompt = (
                "Sen O'zbekiston qishloq xo'jaligi bo'yicha expert agronommisan. "
                "Ushbu rasmda ko'ringan o'simlik yoki kasallikni tahlil qilib, O'zbek tilida yoz:\n\n"
                "1. 🌿 O'simlik turi (agar aniqlansa)\n"
                "2. 🦠 Kasallik yoki muammo (agar mavjud bo'lsa)\n"
                "3. 📋 Kasallik belgilari\n"
                "4. 💊 Davolash usullari va preparatlar\n"
                "5. 🛡 Oldini olish choralari\n"
                "6. ⚠️ Muhim tavsiyalar\n\n"
                "Agar rasm sifatsiz yoki o'simlik ko'rinmasa, shuni ham ayting."
            )
            result = clean_md(await ask_ai(prompt, img_bytes))
            await msg.delete()
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📸 Yana rasm yuborish", callback_data="disease_menu")],
                [InlineKeyboardButton("🏠 Bosh menyu",         callback_data="main_menu")],
            ])
            header = "🦠 <b>O'simlik tahlili natijalari</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            parts  = split_text(result)
            for i, part in enumerate(parts):
                await update.message.reply_text(
                    (header + part) if i == 0 else part,
                    reply_markup=kb if i == len(parts) - 1 else None,
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error(f"Photo handler: {e}")
            await msg.delete()
            await update.message.reply_text(
                "❌ Rasm tahlilida xatolik yuz berdi.\nBiroz kutib qayta urinib ko'ring.",
                reply_markup=main_kb(), parse_mode="HTML",
            )
    else:
        await update.message.reply_text(
            "📸 Rasm qabul qilindi!\n\n"
            "Kasallik aniqlash uchun avval 🦠 <b>Kasallik aniqlash</b> tugmasini bosing.",
            parse_mode="HTML", reply_markup=main_kb(),
        )
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    ai = []
    if GROQ_API_KEY:   ai.append("✅ Groq Vision+Text (asosiy)")
    if GEMINI_API_KEY: ai.append("✅ Gemini Vision+Text")
    if OPENAI_API_KEY: ai.append("✅ OpenAI Text")
    if HF_TOKEN:       ai.append("✅ HF BLIP")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("✅ Smart Dehqon Bot ishga tushdi!")
    logger.info(f"📢 Kanal: {REQUIRED_CHANNEL}")
    logger.info(f"🤖 AI: {' | '.join(ai) if ai else '❌ Kalit yo`q!'}")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
if __name__ == "__main__":
    main()
