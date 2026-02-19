import asyncio
import os
import requests
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
load_dotenv()
from PIL import Image
from urllib.parse import quote_plus


API_URL = "https://router.huggingface.co/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {os.getenv('HF_TOKEN')}",
    "Content-Type": "application/json"
}


OCR_TOKEN = os.getenv("OCR_TOKEN")
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def reset():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Webhook и старые обновления удалены")


# команда /start
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Отправь скрин переписки — я проанализирую 📊")

# обработка фото
@dp.message(F.photo)
async def handle_photo(message: Message):
    await message.answer("📥 Обрабатываю изображение...")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    downloaded_file = await bot.download_file(file.file_path)

    with open("image.jpg", "wb") as f:
        f.write(downloaded_file.read())

    # OCR через OCR.Space
    with open("image.jpg", "rb") as f:
       r = requests.post(
    "https://api.ocr.space/parse/image",
    files={"image": f},
    data={"apikey": OCR_TOKEN, "language": "rus"}  # <- тут OCR_TOKEN
)
    result_json = r.json()
    if result_json["IsErroredOnProcessing"]:
        await message.answer("❌ Ошибка OCR: не удалось распознать текст.")
        return

    text = result_json["ParsedResults"][0]["ParsedText"]
    if not text.strip():
        await message.answer("Не смог прочитать текст 😢 Попробуй другой скрин.")
        return

    # асинхронный вызов анализа
    result = await asyncio.to_thread(analyze_chat, text)
    
    keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
            [
            InlineKeyboardButton(
                text="📤 Поделиться результатом",
                switch_inline_query=result  # вставляет результат в поле ввода другого чата
                )
            ]
        ]
    )
    
    await message.answer(result, reply_markup=keyboard)
    os.remove("image.jpg")

    

# простая функция анализа
def analyze_chat(text):
    try:
        prompt = f"""
Ты — строгий анализатор переписок подростков в Телеграме.

Формат переписки:

Сообщения справа отправлены пользователем бота, слева — собеседником.

Рядом с сообщением есть аватарка и время отправки (24-часовой формат).

Сообщения могут содержать реакции (эмодзи) — учитывай их как позитивные или негативные.

Задача:
Даже если текст неполный или распознан плохо, проанализируй стиль общения, уровень симпатии, интерес собеседников, признаки игнорирования и потенциальные «красные флаги».

Требования к ответу:

Ответ только на русском, строго, максимально коротко и по пунктам.

Не давай лишних объяснений или описаний, только факты.

Формат ответа:
❤️ Симпатия: %
👀 Кто больше заинтересован:
❗ Игнор:
🚩 Рэд флаги:
💡 Совет:

Пример:
❤️ Симпатия: 40%
👀 Кто больше заинтересован: ты
❗ Игнор: слабый
🚩 Рэд флаги: оскорбления
💡 Совет: ищи нового друга

Переписка:
{text}
"""

        response = requests.post(
            API_URL,
            headers=headers,
            json={
                "model": "mistralai/Mistral-7B-Instruct-v0.2",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 500
            }
        )

        if response.status_code != 200:
            return f"Ошибка API: {response.text}"

        data = response.json()
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        return f"Ошибка анализа: {e}"

# endpoint для render/uptime
async def handle(request):
    return web.Response(text="Bot is running")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Webhook удалён")

    # web server для Render
    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print("Бот запущен")

    # polling telegram
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())