import logging
import html
import datetime
import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configuration
TOKEN = os.getenv("8153264069:AAHxdJnYcnx3gHuH9JXn4zcdV52h37EeFhM")
CACHE_DURATION = 1800  # 30 minutes cache
TIMEZONE_OFFSET = 3  # GMT+3 for Saudi Arabia

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global cache
games_cache = {
    'current': [],
    'upcoming': [],
    'timestamp': None
}

def utc_to_local(utc_dt: datetime.datetime) -> datetime.datetime:
    return utc_dt + datetime.timedelta(hours=TIMEZONE_OFFSET)

def format_date(date_str: str) -> str:
    try:
        utc_dt = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        local_dt = utc_to_local(utc_dt)
        return local_dt.strftime("%d/%m/%Y الساعة %I:%M %p (توقيت السعودية)")
    except Exception:
        return date_str

def calculate_time_left(end_date_str: str) -> str:
    try:
        utc_dt = datetime.datetime.strptime(end_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        now = datetime.datetime.utcnow()
        diff = utc_dt - now

        if diff.total_seconds() <= 0:
            return "انتهى العرض"

        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60

        parts = []
        if days > 0:
            parts.append(f"{days} يوم")
        if hours > 0:
            parts.append(f"{hours} ساعة")
        if minutes > 0 or not parts:
            parts.append(f"{minutes} دقيقة")

        return "، ".join(parts)
    except Exception:
        return "غير محسوب"

def get_game_url(game: dict) -> str:
    slug = game.get("productSlug")
    if slug and "edition" not in slug and slug != "[]":
        return f"https://store.epicgames.com/ar/p/{slug}"
    return "https://store.epicgames.com/ar/free-games"

def get_game_image(game: dict) -> str:
    images = game.get("keyImages", [])
    for img_type in ["DieselStoreFrontWide", "OfferImageWide", "Thumbnail"]:
        for img in images:
            if img["type"] == img_type:
                return img["url"]
    return "https://via.placeholder.com/600x400?text=No+Image"

def is_cache_valid() -> bool:
    if not games_cache['timestamp']:
        return False
    age = datetime.datetime.utcnow() - games_cache['timestamp']
    return age.total_seconds() < CACHE_DURATION

def fetch_epic_games() -> tuple:
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
    params = {"locale": "ar", "country": "SA", "allowCountries": "SA"}

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        current_games = []
        upcoming_games = []
        now = datetime.datetime.utcnow().isoformat() + "Z"

        for game in data["data"]["Catalog"]["searchStore"]["elements"]:
            promotions = game.get("promotions")
            if not promotions:
                continue

            if promotions.get("promotionalOffers"):
                offers = promotions["promotionalOffers"][0]["promotionalOffers"]
                if offers:
                    offer = offers[0]
                    start_date = offer["startDate"]
                    end_date = offer["endDate"]

                    if start_date <= now <= end_date:
                        current_games.append({
                            "title": game["title"],
                            "description": game.get("description", "لا يوجد وصف"),
                            "url": get_game_url(game),
                            "image": get_game_image(game),
                            "endDate": end_date
                        })

            if promotions.get("upcomingPromotionalOffers"):
                offers = promotions["upcomingPromotionalOffers"][0]["promotionalOffers"]
                if offers:
                    offer = offers[0]
                    start_date = offer["startDate"]

                    if start_date > now:
                        upcoming_games.append({
                            "title": game["title"],
                            "description": game.get("description", "لا يوجد وصف"),
                            "url": get_game_url(game),
                            "image": get_game_image(game),
                            "startDate": start_date
                        })

        return current_games, upcoming_games

    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        return None, None

def get_cached_games() -> tuple:
    if is_cache_valid():
        return games_cache['current'], games_cache['upcoming']

    current, upcoming = fetch_epic_games()

    if current is not None and upcoming is not None:
        games_cache.update({
            'current': current,
            'upcoming': upcoming,
            'timestamp': datetime.datetime.utcnow()
        })

    return current, upcoming

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_msg = (
        f"🌟 <b>مرحبًا {user.first_name}!</b> 🌟\n\n"
        "أنا بوت <b>Epic Free Games</b> الرسمي 🎮\n"
        "أقدم لك أحدث الألعاب المجانية مباشرة من متجر إيبك جيمز!\n\n"
        "📅 يتم تحديث الألعاب <b>كل يوم خميس</b> الساعة 4:00 مساءً بتوقيت جرينتش\n\n"
        "📌 <b>الأوامر المتاحة:</b>\n"
        "▫️ /start - عرض شاشة البداية\n"
        "▫️ /freegames - الألعاب المجانية الحالية\n"
        "▫️ /next - الألعاب القادمة الأسبوع المقبل\n"
        "▫️ /help - المساعدة والدعم"
    )
    await update.message.reply_text(welcome_msg, parse_mode="HTML")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_msg = (
        "🛟 <b>مركز المساعدة</b>\n\n"
        "▫️ <b>متى يتم تحديث الألعاب؟</b>\n"
        "يتم تحديث الألعاب كل خميس الساعة 4:00 مساءً بتوقيت جرينتش\n\n"
        "▫️ <b>كم مدة بقاء اللعبة مجانية؟</b>\n"
        "كل لعبة تبقى متاحة لمدة أسبوع كامل\n\n"
        "▫️ <b>كيف أحصل على اللعبة؟</b>\n"
        "اضغط على الرابط المرفق مع كل لعبة وقم بتسجيل الدخول بحسابك\n\n"
        "📬 <b>الدعم الفني:</b> @username"
    )
    await update.message.reply_text(help_msg, parse_mode="HTML")

async def free_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 <b>جارٍ تحديث قائمة الألعاب...</b>", parse_mode="HTML")
    current_games, _ = get_cached_games()

    if current_games is None:
        await update.message.reply_text("⚠️ <b>عذراً، حدث خطأ أثناء جلب البيانات</b>", parse_mode="HTML")
        current_games = games_cache.get('current', [])

    if not current_games:
        await update.message.reply_text("📭 <b>لا توجد ألعاب مجانية حالياً</b>", parse_mode="HTML")
        return

    for game in current_games:
        title = html.escape(game["title"])
        description = html.escape(game["description"])[:300]
        message = (
            f"<b>🎮 {title}</b>\n\n"
            f"ℹ️ {description}\n\n"
            f"⏳ تنتهي في: {format_date(game['endDate'])}\n"
            f"⏱ متبقي: {calculate_time_left(game['endDate'])}\n\n"
            f"👉 <a href='{game['url']}'>احصل على اللعبة الآن</a>"
        )
        try:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=game['image'],
                caption=message,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Image Error: {e}")
            await update.message.reply_text(message, parse_mode="HTML")

async def next_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 <b>جارٍ البحث عن الألعاب القادمة...</b>", parse_mode="HTML")
    _, upcoming_games = get_cached_games()

    if upcoming_games is None:
        await update.message.reply_text("⚠️ <b>عذراً، حدث خطأ أثناء جلب البيانات</b>", parse_mode="HTML")
        upcoming_games = games_cache.get('upcoming', [])

    if not upcoming_games:
        await update.message.reply_text("🔮 <b>لا توجد ألعاب قادمة بعد</b>", parse_mode="HTML")
        return

    for game in upcoming_games:
        title = html.escape(game["title"])
        description = html.escape(game["description"])[:300]
        message = (
            f"<b>🎮 {title}</b>\n\n"
            f"ℹ️ {description}\n\n"
            f"⏳ تبدأ في: {format_date(game['startDate'])}\n"
            f"⏱ متبقي: {calculate_time_left(game['startDate'])}\n\n"
            f"👉 <a href='{game['url']}'>صفحة اللعبة</a>"
        )
        try:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=game['image'],
                caption=message,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Image Error: {e}")
            await update.message.reply_text(message, parse_mode="HTML")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("freegames", free_games))
    app.add_handler(CommandHandler("next", next_games))
    logger.info("✅ البوت يعمل الآن...")
    app.run_polling()
