import logging
import os
import io
import time
import base64
import requests
import PIL.Image
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

# Environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL", "@smart_dehqon_channel")
OWM_API_KEY = os.environ.get("OWM_API_KEY", "")

# Validate required environment variables
if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
    raise ValueError("❌ BOT_TOKEN sozlanmagan!")

if not GEMINI_API_KEY and not OPENAI_API_KEY and not HF_TOKEN:
    logger.warning("⚠️ Hech qanday AI API kaliti sozlanmagan!")

# Hugging Face API configurations (fallback uchun)
HF_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
HF_IMAGE_API_URL = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"

HF_HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}"
}

# Gemini API
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

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
    try:
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
        desc = desc_list[0].get("value", "") if desc_list else "Ma'lumot yo'q"

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
    except Exception as e:
        logger.error(f"wttr.in error: {e}")
        return "❌ Ob-havo ma'lumotini olishda xatolik."

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

def ask_gemini_text(prompt: str) -> str:
    """Google Gemini API dan matnli javob olish"""
    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY sozlanmagan")

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        }
    }

    response = requests.post(
        f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
        json=payload,
        timeout=30
    )

    if response.status_code != 200:
        logger.error(f"Gemini API error: {response.status_code} - {response.text[:200]}")
        raise Exception(f"Gemini API xatosi: {response.status_code}")

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise Exception("Gemini bo'sh javob qaytardi")

    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    if not parts:
        raise Exception("Gemini javob qismlari bo'sh")

    return parts[0].get("text", "").strip()

def ask_gemini_vision(prompt: str, image_bytes: bytes) -> str:
    """Google Gemini Vision API dan rasm tahlili"""
    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY sozlanmagan")

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_b64
                        }
                    },
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 2048,
        }
    }

    vision_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    response = requests.post(
        f"{vision_url}?key={GEMINI_API_KEY}",
        json=payload,
        timeout=40
    )

    if response.status_code != 200:
        logger.error(f"Gemini Vision error: {response.status_code} - {response.text[:200]}")
        raise Exception(f"Gemini Vision API xatosi: {response.status_code}")

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise Exception("Gemini Vision bo'sh javob qaytardi")

    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    if not parts:
        raise Exception("Gemini Vision javob qismlari bo'sh")

    return parts[0].get("text", "").strip()

def ask_openai_text(prompt: str) -> str:
    """OpenAI API dan matnli javob olish (fallback)"""
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY sozlanmagan")

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2048,
        "temperature": 0.7
    }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=30
    )

    if response.status_code != 200:
        logger.error(f"OpenAI API error: {response.status_code} - {response.text[:200]}")
        raise Exception(f"OpenAI API xatosi: {response.status_code}")

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()

def ask_hf_text(prompt: str) -> str:
    """Hugging Face API dan matnli javob olish (oxirgi fallback)"""
    if not HF_TOKEN:
        raise Exception("HF_TOKEN sozlanmagan")

    # Mistral modeli uchun instruction format
    formatted_prompt = f"[INST] {prompt} [/INST]"

    response = requests.post(
        HF_API_URL,
        headers=HF_HEADERS,
        json={
            "inputs": formatted_prompt,
            "parameters": {
                "max_new_tokens": 1024,
                "temperature": 0.7,
                "return_full_text": False
            }
        },
        timeout=60
    )

    if response.status_code == 503:
        # Model yuklanmoqda, biroz kutish
        logger.warning("HF model yuklanmoqda, 20s kutilmoqda...")
        time.sleep(20)
        response = requests.post(
            HF_API_URL,
            headers=HF_HEADERS,
            json={
                "inputs": formatted_prompt,
                "parameters": {
                    "max_new_tokens": 1024,
                    "temperature": 0.7,
                    "return_full_text": False
                }
            },
            timeout=60
        )

    if response.status_code != 200:
        raise Exception(f"HF API xatosi: {response.status_code}")

    result = response.json()
    if isinstance(result, list) and len(result) > 0:
        return result[0].get("generated_text", "").strip()
    raise Exception("HF API bo'sh javob qaytardi")

async def ask_ai(prompt: str, image_bytes: bytes = None) -> str:
    """
    AI javob olish - Gemini > OpenAI > HF tartibida urinadi.
    Rasm yuborilsa - Gemini Vision ishlatiladi.
    """
    errors = []

    # === RASM TAHLILI ===
    if image_bytes:
        # 1. Gemini Vision (asosiy)
        if GEMINI_API_KEY:
            try:
                result = ask_gemini_vision(prompt, image_bytes)
                if result:
                    logger.info("✅ Gemini Vision ishlatildi")
                    return result
            except Exception as e:
                logger.warning(f"Gemini Vision xatolik: {e}")
                errors.append(f"Gemini Vision: {e}")

        # 2. HF Image fallback
        if HF_TOKEN:
            try:
                response = requests.post(
                    HF_IMAGE_API_URL,
                    headers=HF_HEADERS,
                    data=image_bytes,
                    timeout=40
                )
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, list) and result:
                        caption = result[0].get("generated_text", "")
                        if caption:
                            # Gemini text bilan tahlil qilamiz
                            if GEMINI_API_KEY:
                                detail_prompt = (
                                    f"Rasm tavsifi: '{caption}'\n\n"
                                    f"Sen O'zbekiston qishloq xo'jaligi bo'yicha expert agronommisan. "
                                    f"Ushbu rasmda ko'ringan o'simlik yoki kasallik haqida O'zbek tilida batafsil yoz:\n"
                                    f"1. O'simlik/kasallik nomi\n"
                                    f"2. Kasallik belgilari\n"
                                    f"3. Davolash usullari\n"
                                    f"4. Oldini olish choralari\n"
                                    f"5. Tavsiya etiladigan preparatlar"
                                )
                                try:
                                    return ask_gemini_text(detail_prompt)
                                except Exception:
                                    pass
                            return f"🔍 Rasm tahlili: {caption}"
                logger.warning(f"HF Image xatolik: {response.status_code}")
            except Exception as e:
                logger.warning(f"HF Image xatolik: {e}")
                errors.append(f"HF Image: {e}")

        return "❌ Rasm tahlilida muammo yuz berdi. Boshqa aniqroq rasm yuborib ko'ring."

    # === MATNLI SO'ROV ===

    # 1. Gemini (asosiy va eng ishonchli)
    if GEMINI_API_KEY:
        try:
            result = ask_gemini_text(prompt)
            if result:
                logger.info("✅ Gemini API ishlatildi")
                return result
        except Exception as e:
            logger.warning(f"Gemini xatolik: {e}")
            errors.append(f"Gemini: {e}")

    # 2. OpenAI (ikkinchi)
    if OPENAI_API_KEY:
        try:
            result = ask_openai_text(prompt)
            if result:
                logger.info("✅ OpenAI API ishlatildi")
                return result
        except Exception as e:
            logger.warning(f"OpenAI xatolik: {e}")
            errors.append(f"OpenAI: {e}")

    # 3. Hugging Face (oxirgi fallback)
    if HF_TOKEN:
        try:
            result = ask_hf_text(prompt)
            if result:
                logger.info("✅ HF API ishlatildi")
                return result
        except Exception as e:
            logger.warning(f"HF xatolik: {e}")
            errors.append(f"HF: {e}")

    logger.error(f"Barcha AI xizmatlari ishlamadi: {errors}")
    return (
        "❌ Hozirda AI xizmati vaqtinchalik ishlamayapti.\n\n"
        "Iltimos, bir necha daqiqadan so'ng qayta urinib ko'ring.\n"
        "Muammo davom etsa, admin bilan bog'laning."
    )

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
    if page < 0 or len(BOOKS) == 0:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
        ])

    start = page * BOOKS_PER_PAGE
    end = min(start + BOOKS_PER_PAGE, len(BOOKS))
    keyboard = []

    for i in range(start, end):
        if i < len(BOOKS):
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
            await query.answer("Xatolik: Viloyat topilmadi", show_alert=True)
            return

        region_name = region_keys[idx]
        region_info = REGIONS[region_name]

        await query.edit_message_text(
            f"⏳ <b>{region_name}</b> ob-havosi yuklanmoqda...",
            parse_mode="HTML"
        )

        try:
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
        except Exception as e:
            logger.error(f"Weather error: {e}")
            await query.edit_message_text(
                f"❌ Ob-havo ma'lumotini olishda xatolik.\n{str(e)}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Orqaga", callback_data="weather_menu")]
                ])
            )

    elif data == "ekish_menu":
        context.user_data["state"] = "waiting_ekish"
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

    elif data == "disease_menu":
        context.user_data["state"] = "waiting_disease_photo"
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

    elif data.startswith("books_menu_"):
        page_str = data.replace("books_menu_", "")
        if not page_str.isdigit():
            await query.answer("Xatolik!", show_alert=True)
            return

        page = int(page_str)
        total_pages = (len(BOOKS) - 1) // BOOKS_PER_PAGE + 1 if BOOKS else 1
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
        context.user_data["state"] = ""
        ekin_nomi = update.message.text.strip()

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
            f"Javob O'zbekiston iqlimi va sharoitiga mos, aniq va amaliy bo'lsin."
        )

        result = await ask_ai(prompt)
        result = clean_markdown(result)

        header = f"🌱 <b>{ekin_nomi.upper()} — Ekish tavsiyasi</b>\n\n"
        parts = split_text(result)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌱 Boshqa ekin so'rash", callback_data="ekish_menu")],
            [InlineKeyboardButton("🏠 Bosh menu", callback_data="main_menu")]
        ])

        try:
            await msg.edit_text(
                header + parts[0],
                reply_markup=None if len(parts) > 1 else keyboard,
                parse_mode="HTML"
            )

            for i in range(1, len(parts)):
                is_last = (i == len(parts) - 1)
                await update.message.reply_text(
                    parts[i],
                    reply_markup=keyboard if is_last else None,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Message edit error: {e}")
            await msg.delete()
            await update.message.reply_text(
                header + result[:3800],
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    else:
        await update.message.reply_text(
            "📋 Menyu orqali bo'lim tanlang:",
            reply_markup=get_main_menu(),
            parse_mode="HTML"
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

        try:
            photo = update.message.photo[-1]
            file = await photo.get_file()
            image_bytes = bytes(await file.download_as_bytearray())

            prompt = (
                "Sen O'zbekiston qishloq xo'jaligi bo'yicha expert agronommisan. "
                "Ushbu rasmda ko'ringan o'simlik yoki kasallikni tahlil qilib, O'zbek tilida quyidagilarni yoz:\n\n"
                "1. 🌿 O'simlik turi (agar aniqlanса)\n"
                "2. 🦠 Kasallik yoki muammo (agar mavjud bo'lsa)\n"
                "3. 📋 Kasallik belgilari\n"
                "4. 💊 Davolash usullari va preparatlar\n"
                "5. 🛡 Oldini olish choralari\n"
                "6. ⚠️ Muhim tavsiyalar\n\n"
                "Agar rasm o'simlik emas bo'lsa yoki sifatsiz bo'lsa, shuni ham ayting."
            )

            result = await ask_ai(prompt, image_bytes)
            result = clean_markdown(result)

            await msg.delete()

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📸 Yana rasm yuborish", callback_data="disease_menu")],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")],
            ])

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

        except Exception as e:
            logger.error(f"Photo handler error: {e}")
            await msg.delete()
            await update.message.reply_text(
                f"❌ Rasm tahlilida xatolik yuz berdi.\n\nBiroz kutib qayta urinib ko'ring.",
                reply_markup=get_main_menu(),
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
    try:
        app = Application.builder().token(BOT_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

        logger.info("✅ Smart Dehqon Bot ishga tushdi!")
        logger.info(f"📢 Obuna kanali: {REQUIRED_CHANNEL}")
        if GEMINI_API_KEY:
            logger.info("✅ Gemini API ulandi (asosiy AI)")
        if OPENAI_API_KEY:
            logger.info("✅ OpenAI API ulandi (zaxira AI)")
        if HF_TOKEN:
            logger.info("✅ Hugging Face ulandi (oxirgi zaxira)")

        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.critical(f"❌ Bot startup error: {e}")
        raise

if __name__ == "__main__":
    main()
