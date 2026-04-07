import os
import io
import time
import logging
import requests
import PIL.Image
import google.genai as genai
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

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8750814350:AAHnMY9oVpCY7IRCHdBXfas_Wg__oxQRzAM")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL", "@smart_dehqon_channel")
OWM_API_KEY = os.environ.get("OWM_API_KEY", "")

REGIONS = {
    "🏙 Toshkent sh.": {"city": "Tashkent", "lat": 41.2995, "lon": 69.2401},
    "🌆 Toshkent v.": {"city": "Chirchiq", "lat": 41.4694, "lon": 69.5833},
    "🌿 Samarqand": {"city": "Samarkand", "lat": 39.6542, "lon": 66.9597},
    "🕌 Buxoro": {"city": "Bukhara", "lat": 39.7747, "lon": 64.4286},
    "⛰ Namangan": {"city": "Namangan", "lat": 41.0011, "lon": 71.6722},
    "🏔 Andijon": {"city": "Andijan", "lat": 40.7821, "lon": 72.3442},
    "🌾 Farg'ona": {"city": "Fergana", "lat": 40.3842, "lon": 71.7843},
    "🌵 Qashqadaryo": {"city": "Qarshi", "lat": 38.8600, "lon": 65.7897},
    "☀️ Surxondaryo": {"city": "Termez", "lat": 37.2242, "lon": 67.2783},
    "🌊 Xorazm": {"city": "Urgench", "lat": 41.5500, "lon": 60.6333},
    "⛏ Navoiy": {"city": "Navoi", "lat": 40.0843, "lon": 65.3791},
    "🌱 Jizzax": {"city": "Jizzakh", "lat": 40.1158, "lon": 67.8422},
    "🚜 Sirdaryo": {"city": "Gulistan", "lat": 40.4897, "lon": 68.7842},
    "🏜 Qoraqalpog'iston": {"city": "Nukus", "lat": 42.4533, "lon": 59.6139},
}

WEATHER_ICONS = {
    "01": "☀️", "02": "⛅", "03": "🌥", "04": "☁️",
    "09": "🌧", "10": "🌦", "11": "⛈", "13": "❄️", "50": "🌫",
}

def get_weather_icon(icon_code: str) -> str:
    prefix = icon_code[:2]
    return WEATHER_ICONS.get(prefix, "🌡")

def get_weather(lat: float, lon: float, city_name: str) -> str:
    try:
        if OWM_API_KEY:
            return get_weather_owm(lat, lon)
        else:
            return get_weather_wttr(city_name)
    except Exception as e:
        logger.error(f"Weather error: {e}")
        return "❌ Ob-havo ma'lumotini olishda xatolik. Keyinroq urinib ko'ring."

def get_weather_owm(lat: float, lon: float) -> str:
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/forecast"
            f"?lat={lat}&lon={lon}&appid={OWM_API_KEY}&units=metric&lang=uz&cnt=24"
        )
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("cod") != "200":
            raise Exception(data.get("message", "API error"))

        current = data["list"][0]
        temp = round(current["main"]["temp"])
        feels = round(current["main"]["feels_like"])
        humidity = current["main"]["humidity"]
        wind = round(current["wind"]["speed"] * 3.6)
        desc = current["weather"][0]["description"].capitalize()
        icon = get_weather_icon(current["weather"][0]["icon"])
        pressure = current["main"]["pressure"]

        days = {}
        for item in data["list"]:
            date = item["dt_txt"][:10]
            if date not in days:
                days[date] = {"min": [], "max": [], "desc": "", "icon": ""}
            days[date]["min"].append(item["main"]["temp_min"])
            days[date]["max"].append(item["main"]["temp_max"])
            days[date]["desc"] = item["weather"][0]["description"].capitalize()
            days[date]["icon"] = get_weather_icon(item["weather"][0]["icon"])

        forecast = ""
        for i, (date, d) in enumerate(list(days.items())[:4]):
            if i == 0:
                continue
            mn = round(min(d["min"]))
            mx = round(max(d["max"]))
            forecast += f"\n{d['icon']} {date}: {mn}°C ~ {mx}°C | {d['desc']}"

        return (
            f"{icon} <b>Hozirgi holat:</b> {desc}\n"
            f"🌡 Harorat: <b>{temp}°C</b> (his: {feels}°C)\n"
            f"💧 Namlik: <b>{humidity}%</b>\n"
            f"💨 Shamol: <b>{wind} km/soat</b>\n"
            f"🔵 Bosim: <b>{pressure} hPa</b>\n\n"
            f"📅 <b>Kelgusi kunlar:</b>{forecast}"
        )
    except Exception as e:
        logger.error(f"OWM error: {e}")
        raise

def get_weather_wttr(city: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 AgroBot/1.0"}
    resp = requests.get(
        f"https://wttr.in/{city}?format=j1",
        headers=headers,
        timeout=15
    )
    resp.raise_for_status()
    data = resp.json()
    current = data["current_condition"][0]
    temp = current["temp_C"]
    feels = current["FeelsLikeC"]
    humidity = current["humidity"]
    wind = current["windspeedKmph"]
    pressure = current["pressure"]
    desc_list = current.get("weatherDesc", [{}])
    desc = desc_list[0].get("value", "") if desc_list else ""
    weather3day = data.get("weather", [])
    forecast_text = ""
    for i, day in enumerate(weather3day):
        if i == 0:
            continue
        date = day["date"]
        max_t = day["maxtempC"]
        min_t = day["mintempC"]
        desc_day = day["hourly"][4].get("weatherDesc", [{}])[0].get("value", "")
        forecast_text += f"\n☁️ {date}: {min_t}°C ~ {max_t}°C | {desc_day}"
    return (
        f"☀️ <b>Hozirgi holat:</b> {desc}\n"
        f"🌡 Harorat: <b>{temp}°C</b> (his: {feels}°C)\n"
        f"💧 Namlik: <b>{humidity}%</b>\n"
        f"💨 Shamol: <b>{wind} km/soat</b>\n"
        f"🔵 Bosim: <b>{pressure} hPa</b>\n\n"
        f"📅 <b>Kelgusi kunlar:</b>{forecast_text}"
    )

def clean_markdown(text: str) -> str:
    import re
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    text = re.sub(r'#{1,6}\s+(.+)', r'<b>\1</b>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    return text

def split_text(text: str, max_len: int = 3800) -> list:
    if len(text) <= max_len:
        return [text]
    parts = []
    while len(text) > max_len:
        split_at = text.rfind('\n', 0, max_len)
        if split_at == -1:
            split_at = max_len
        parts.append(text[:split_at])
        text = text[split_at:].lstrip('\n')
    if text:
        parts.append(text)
    return parts

def ai_analyze(prompt: str, image_bytes: bytes = None) -> str:
    if not GEMINI_API_KEY:
        return "❌ Gemini AI kaliti sozlanmagan."
    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-2.0-flash"]
    client = genai.Client(api_key=GEMINI_API_KEY)
    last_error = ""
    for model in models_to_try:
        try:
            if image_bytes:
                image = PIL.Image.open(io.BytesIO(image_bytes))
                response = client.models.generate_content(
                    model=model,
                    contents=[prompt, image]
                )
            else:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt
                )
            return response.text
        except Exception as e:
            err = str(e)
            logger.error(f"Gemini [{model}] error: {err}")
            last_error = err
            if "429" in err:
                time.sleep(2)
                continue
            break
    return f"❌ AI xizmatida vaqtinchalik muammo. Biroz kutib qayta urinib ko'ring."

async def is_subscribed(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return member.status in [
            ChatMember.MEMBER,
            ChatMember.ADMINISTRATOR,
            ChatMember.OWNER,
        ]
    except Exception as e:
        logger.warning(f"Subscription check error: {e}")
        return False

def get_subscribe_keyboard():
    channel_link = (
        REQUIRED_CHANNEL
        if REQUIRED_CHANNEL.startswith("http")
        else f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"
    )
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=channel_link)],
        [InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub")],
    ])

def get_not_subscribed_text():
    return (
        "⚠️ <b>Botdan foydalanish uchun avval kanalga obuna bo'ling!</b>\n\n"
        f"📢 Kanal: {REQUIRED_CHANNEL}\n\n"
        "Obuna bo'lgach ✅ <b>Obunani tekshirish</b> tugmasini bosing."
    )

def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌤 Ob-havo", callback_data="weather_menu")],
        [InlineKeyboardButton("🌱 Ekish tavsiyasi (AI)", callback_data="ekish_menu")],
        [InlineKeyboardButton("🦠 Kasallik aniqlash (AI)", callback_data="disease_menu")],
        [InlineKeyboardButton("📚 Kitoblar menyusi", callback_data="books_menu_0")],
    ])

def get_weather_menu():
    keyboard = []
    region_list = list(REGIONS.keys())
    for i in range(0, len(region_list), 2):
        row = [InlineKeyboardButton(region_list[i], callback_data=f"weather_{i}")]
        if i + 1 < len(region_list):
            row.append(InlineKeyboardButton(region_list[i+1], callback_data=f"weather_{i+1}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_books_menu(page: int):
    start = page * BOOKS_PER_PAGE
    end = min(start + BOOKS_PER_PAGE, len(BOOKS))
    keyboard = []
    for i in range(start, end):
        title, url = BOOKS[i]
        keyboard.append([InlineKeyboardButton(f"{i+1}. {title[:45]}", url=url)])
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Oldingi", callback_data=f"books_menu_{page-1}"))
    if end < len(BOOKS):
        nav_row.append(InlineKeyboardButton("Keyingi ▶️", callback_data=f"books_menu_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_subscribed(user.id, context):
        await update.message.reply_text(
            get_not_subscribed_text(),
            reply_markup=get_subscribe_keyboard(),
            parse_mode="HTML"
        )
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
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "check_sub":
        if await is_subscribed(user_id, context):
            user = update.effective_user
            await query.edit_message_text(
                f"✅ <b>Tabriklaymiz, {user.first_name}!</b>\n\n"
                "Obuna tasdiqlandi. Botdan to'liq foydalanishingiz mumkin!\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🌤 <b>Ob-havo</b> — 14 viloyat uchun real vaqt\n"
                "🌱 <b>Ekish tavsiyasi</b> — AI yordamida professional tavsiya\n"
                "🦠 <b>Kasallik aniqlash</b> — Rasm orqali AI tahlil\n"
                "📚 <b>Kitoblar</b> — 122 ta qishloq xo'jaligi kitobi\n"
                "━━━━━━━━━━━━━━━━━━━━",
                reply_markup=get_main_menu(),
                parse_mode="HTML"
            )
        else:
            await query.answer("❌ Siz hali obuna bo'lmagansiz!", show_alert=True)
        return

    if not await is_subscribed(user_id, context):
        await query.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
        await query.edit_message_text(
            get_not_subscribed_text(),
            reply_markup=get_subscribe_keyboard(),
            parse_mode="HTML"
        )
        return

    if data == "main_menu":
        await query.edit_message_text(
            "🌾 <b>Smart Dehqon Bot</b> — Asosiy menyu\n\n"
            "Quyidagi bo'limdan birini tanlang 👇",
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )

    elif data == "weather_menu":
        await query.edit_message_text(
            "🌤 <b>Ob-havo</b>\n\n"
            "Qaysi viloyatni ko'rmoqchisiz?\n"
            "Viloyatni tanlang 👇",
            reply_markup=get_weather_menu(),
            parse_mode="HTML"
        )

    elif data.startswith("weather_") and data[8:].isdigit():
        idx = int(data[8:])
        region_keys = list(REGIONS.keys())
        if idx >= len(region_keys):
            return
        region_name = region_keys[idx]
        region_info = REGIONS[region_name]
        await query.edit_message_text(
            f"⏳ <b>{region_name}</b> ob-havosi yuklanmoqda...",
            parse_mode="HTML"
        )
        weather_text = get_weather(region_info["lat"], region_info["lon"], region_info["city"])
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Yangilash", callback_data=data)],
            [InlineKeyboardButton("⬅️ Viloyatlar", callback_data="weather_menu")],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")],
        ])
        await query.edit_message_text(
            f"🌤 <b>{region_name} ob-havosi</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{weather_text}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    elif data == "ekish_menu":
        await query.edit_message_text(
            "🌱 <b>Ekish tavsiyasi (AI)</b>\n\n"
            "Qaysi ekin haqida ma'lumot olmoqchisiz?\n\n"
            "📝 Masalan:\n"
            "• <i>G'o'za</i>\n"
            "• <i>Bug'doy</i>\n"
            "• <i>Pomidor</i>\n"
            "• <i>Kartoshka</i>\n"
            "• <i>Sholi</i>\n\n"
            "Ekin nomini yozing 👇",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
            ]),
            parse_mode="HTML"
        )
        context.user_data["state"] = "waiting_ekish"

    elif data == "disease_menu":
        await query.edit_message_text(
            "🦠 <b>O'simlik kasalligini aniqlash (AI)</b>\n\n"
            "O'simlik yoki bargning <b>aniq, yorug'</b> rasmini yuboring.\n"
            "AI kasallikni aniqlab, davolash usulini tavsiya qiladi.\n\n"
            "📸 <b>Rasmni yuboring</b> 👇",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
            ]),
            parse_mode="HTML"
        )
        context.user_data["state"] = "waiting_disease_photo"

    elif data.startswith("books_menu_"):
        page = int(data.replace("books_menu_", ""))
        total_pages = (len(BOOKS) - 1) // BOOKS_PER_PAGE + 1
        start_idx = page * BOOKS_PER_PAGE + 1
        end_idx = min((page + 1) * BOOKS_PER_PAGE, len(BOOKS))
        await query.edit_message_text(
            f"📚 <b>Qishloq xo'jaligi kitoblari</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Sahifa {page+1}/{total_pages} | {start_idx}–{end_idx}-kitoblar\n\n"
            f"Kitob nomiga bosib PDF yuklab olishingiz mumkin 👇",
            reply_markup=get_books_menu(page),
            parse_mode="HTML"
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context):
        await update.message.reply_text(
            get_not_subscribed_text(),
            reply_markup=get_subscribe_keyboard(),
            parse_mode="HTML"
        )
        return

    state = context.user_data.get("state", "")

    if state == "waiting_ekish":
        ekin_nomi = update.message.text.strip()
        context.user_data["state"] = ""
        msg = await update.message.reply_text(
            f"⏳ <b>{ekin_nomi}</b> uchun AI tavsiya tayyorlanmoqda...\n"
            "Bu bir necha soniya olishi mumkin.",
            parse_mode="HTML"
        )
        prompt = (
            f"Sen O'zbekiston qishloq xo'jaligi bo'yicha professional agronommisan. "
            f"'{ekin_nomi}' ekini uchun quyidagilarni O'zbek tilida batafsil va professional tarzda yoz:\n\n"
            f"1. 📅 Ekish vaqti (oylar ko'rsatilsin)\n"
            f"2. 🌱 Tuproq tayyorlash (haydash, o'g'itlash)\n"
            f"3. 💧 Sug'orish rejimi (necha kundan bir, qancha)\n"
            f"4. 🧪 O'g'itlash tavsiyasi (NPK miqdorlari)\n"
            f"5. 🌿 Parvarishlash (o't o'chirish, ishlash)\n"
            f"6. 🌾 Yig'im-terim vaqti\n"
            f"7. 🦠 Asosiy kasalliklar va zararkunandalar\n"
            f"8. ⚠️ Muhim ogohlantirishlar\n\n"
            f"Javob O'zbekiston iqlimi va sharoitiga mos, aniq va amaliy bo'lsin. "
            f"Har bir bandni alohida yoz."
        )
        result = ai_analyze(prompt)
        result = clean_markdown(result)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌱 Boshqa ekin so'rash", callback_data="ekish_menu")],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")],
        ])
        await msg.delete()
        header = f"🌱 <b>{ekin_nomi.upper()} — Ekish tavsiyasi</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        parts = split_text(result)
        for i, part in enumerate(parts):
            is_last = (i == len(parts) - 1)
            text = (header + part) if i == 0 else part
            await update.message.reply_text(
                text,
                reply_markup=keyboard if is_last else None,
                parse_mode="HTML"
            )
    else:
        await update.message.reply_text(
            "Iltimos, quyidagi menyudan birini tanlang 👇",
            reply_markup=get_main_menu()
        )

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context):
        await update.message.reply_text(
            get_not_subscribed_text(),
            reply_markup=get_subscribe_keyboard(),
            parse_mode="HTML"
        )
        return

    state = context.user_data.get("state", "")

    if state == "waiting_disease_photo":
        context.user_data["state"] = ""
        msg = await update.message.reply_text(
            "🔍 Rasm tahlil qilinmoqda...\n"
            "AI o'simlikni ko'rib chiqmoqda, biroz kuting."
        )
        photo = update.message.photo[-1]
        file = await photo.get_file()
        image_bytes = bytes(await file.download_as_bytearray())

        prompt = (
            "Sen o'simlik kasalliklari bo'yicha professional fitopatalogsan. "
            "Bu rasmni sinchkovlik bilan ko'rib chiqib, O'zbek tilida quyidagilarni batafsil yoz:\n\n"
            "1. 🌿 O'simlik turi (agar aniqlanib bo'lsa)\n"
            "2. 🔎 Ko'rinayotgan belgilar (ranglar, dog'lar, deformatsiya va h.k.)\n"
            "3. 🦠 Kasallik nomi (agar aniqlanib bo'lsa)\n"
            "4. ⚗️ Kasallik sababi (virus, bakteriya, zamburug', fitofag va h.k.)\n"
            "5. 💊 Davolash usuli (kimyoviy va biologik preparatlar)\n"
            "6. 🛡 Oldini olish choralari\n"
            "7. ⚠️ Qo'shni o'simliklarga xavfi\n\n"
            "Agar o'simlik sog'lom ko'rinsa, buni ham aniq aytib o't va parvarishlash tavsiyalari ber. "
            "Javob professional va aniq bo'lsin."
        )
        result = ai_analyze(prompt, image_bytes)
        result = clean_markdown(result)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📸 Yana rasm yuborish", callback_data="disease_menu")],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")],
        ])
        await msg.delete()
        header = "🦠 <b>O'simlik tahlili natijalari</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        parts = split_text(result)
        for i, part in enumerate(parts):
            is_last = (i == len(parts) - 1)
            text = (header + part) if i == 0 else part
            await update.message.reply_text(
                text,
                reply_markup=keyboard if is_last else None,
                parse_mode="HTML"
            )
    else:
        await update.message.reply_text(
            "📸 Rasm qabul qilindi!\n\n"
            "Kasallik aniqlash uchun avval 🦠 <b>Kasallik aniqlash</b> tugmasini bosing.",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN sozlanmagan!")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("✅ Smart Dehqon Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
# update
if __name__ == "__main__":
    main()
