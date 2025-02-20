import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import yt_dlp
import os

# Ваш токен Telegram-бота
TELEGRAM_TOKEN = '8026415349:AAFEa9tHgFXlkYVM-k7NLI_5hjRMbYa_jTQ'

# Инициализация бота
application = Application.builder().token(TELEGRAM_TOKEN).build()


# Функция для поиска песен на YouTube
def search_youtube(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'default_search': 'ytsearch5',  # Ограничиваем до 5 результатов
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(query, download=False)  # Не скачиваем, только ищем
            return result['entries']  # Возвращаем список результатов
    except Exception as e:
        print(f"Ошибка при поиске: {e}")
        return []


# Функция для скачивания выбранной песни
def download_youtube_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': './%(title)s.%(ext)s',
        'quiet': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace('.webm', '.mp3')
            return filename
    except Exception as e:
        print(f"Ошибка при скачивании: {e}")
        return None


# Команда /start
async def start(update, context):
    await update.message.reply_text('Привет! Напишите название песни или часть текста, чтобы найти её.')


# Обработка текстового запроса
async def search(update, context):
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text('Пожалуйста, введите запрос для поиска!')
        return

    await update.message.reply_text('Ищу варианты, подождите...')
    results = search_youtube(query)

    if not results:
        await update.message.reply_text('Ничего не найдено. Попробуйте другой запрос.')
        return

    # Формируем inline-кнопки с результатами
    keyboard = []
    for idx, entry in enumerate(results):
        title = entry.get('title', 'Без названия')
        video_id = entry.get('id')
        keyboard.append([InlineKeyboardButton(f"{idx + 1}. {title[:50]}...", callback_data=f"select_{video_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Выберите песню:', reply_markup=reply_markup)


# Обработка выбора пользователя
async def button(update, context):
    query = update.callback_query
    data = query.data
    chat_id = query.message.chat_id

    if data.startswith('select_'):
        video_id = data.split('_')[1]
        url = f"https://www.youtube.com/watch?v={video_id}"

        # Показываем кнопки для действий с выбранной песней
        keyboard = [
            [InlineKeyboardButton("Скачать", callback_data=f"download_{video_id}")],
            [InlineKeyboardButton("Отмена", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Вы выбрали эту песню. Что дальше?", reply_markup=reply_markup)

    elif data.startswith('download_'):
        video_id = data.split('_')[1]
        url = f"https://www.youtube.com/watch?v={video_id}"
        await query.edit_message_text(text="Скачиваю песню, подождите...")

        file_path = download_youtube_audio(url)
        if file_path and os.path.exists(file_path):
            await context.bot.send_audio(chat_id=chat_id, audio=open(file_path, 'rb'))
            os.remove(file_path)
            await context.bot.send_message(chat_id=chat_id, text="Готово!")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Не удалось скачать песню.")

    elif data == 'cancel':
        await query.edit_message_text(text="Действие отменено.")


# Регистрация обработчиков
application.add_handler(CommandHandler('start', start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
application.add_handler(CallbackQueryHandler(button))

# Запуск бота с polling
application.run_polling()