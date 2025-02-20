import os
import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
import random
import asyncio
import shutil
from transformers import pipeline
import aiohttp

# Константы
API_TOKEN = '8026415349:AAFEa9tHgFXlkYVM-k7NLI_5hjRMbYa_jTQ'  # Замените на ваш токен
MOVIE_URL = 'https://thegirl.ru/articles/100-filmov-kotorye-stoit-posmotret-kazhdomu/'
MOTIVATION_URL = "https://vc.ru/flood/797499-podborka-100-motivacionnyh-fraz-na-vse-sluchai-zhizni-mozhno-prochitat-vse-100-srazu"
PARSE_MODE = 'MarkdownV2'

# Инициализация бота и нейросети
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
nlp = pipeline("question-answering", model="distilbert-base-uncased-distilled-squad")

async def search_and_download_images(query, num_images):
    """Поиск изображений через Google Images с попыткой высокого качества."""
    if num_images <= 0 or num_images > 10:
        return [], None
    search_url = f"https://www.google.com/search?hl=en&q={requests.utils.quote(query)}&tbm=isch&tbs=isz:l"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    temp_dir = f"temp_{query}_{random.randint(1000, 9999)}"
    os.makedirs(temp_dir, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(search_url, headers=headers) as response:
                response.raise_for_status()
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                img_tags = soup.find_all("img")[1:num_images + 1]

                image_paths = []
                for i, img_tag in enumerate(img_tags):
                    img_url = img_tag.get('src') or img_tag.get('data-src')
                    if not img_url or not img_url.startswith('http'):
                        continue
                    try:
                        async with session.get(img_url, headers=headers) as img_response:
                            img_data = await img_response.read()
                            img_path = os.path.join(temp_dir, f'image_{i + 1}.jpg')
                            with open(img_path, 'wb') as img_file:
                                img_file.write(img_data)
                            image_paths.append(img_path)
                    except aiohttp.ClientError as e:
                        print(f"Не удалось скачать изображение {i + 1}: {e}")

                if len(image_paths) < num_images:
                    links = soup.find_all('a', href=True)
                    for link in links[:num_images - len(image_paths)]:
                        href = link['href']
                        if 'imgurl=' in href:
                            img_url = href.split('imgurl=')[1].split('&')[0]
                            try:
                                async with session.get(img_url) as img_response:
                                    img_data = await img_response.read()
                                    img_path = os.path.join(temp_dir, f'image_{len(image_paths) + 1}.jpg')
                                    with open(img_path, 'wb') as img_file:
                                        img_file.write(img_data)
                                    image_paths.append(img_path)
                            except aiohttp.ClientError as e:
                                print(f"Не удалось скачать полноразмерное изображение: {e}")

                return image_paths, temp_dir
        except aiohttp.ClientError as e:
            print(f"Ошибка при поиске изображений: {e}")
            return [], temp_dir

def get_movies():
    """Получение списка фильмов с сайта."""
    try:
        response = requests.get(MOVIE_URL, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        movies = []
        for h2 in soup.find_all('h2'):
            title = h2.get_text(strip=True)
            if not title or title.isdigit():
                continue
            div_block = h2.find_next('div', class_='block-text')
            description = div_block.find('p').get_text(strip=True) if div_block and div_block.find('p') else "Описание отсутствует"
            movies.append((title, description))
        return movies
    except requests.RequestException as e:
        print(f"Ошибка при загрузке фильмов: {e}")
        return []

def get_motivation():
    """Получение мотивационных фраз."""
    try:
        response = requests.get(MOTIVATION_URL, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        quotes = [li.get_text(strip=True) for li in soup.find_all('li') if li.get_text(strip=True)]
        return quotes if quotes else ["Мотивация временно недоступна."]
    except requests.RequestException as e:
        print(f"Ошибка при загрузке мотивации: {e}")
        return ["Не удалось загрузить мотивацию."]

def escape_markdown_v2(text):
    """Экранирование всех специальных символов для MarkdownV2."""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def translate_text(text, target_lang="en"):
    """Перевод текста с помощью бесплатного API."""
    url = f"https://api.mymemory.translated.net/get?q={requests.utils.quote(text)}&langpair=ru|{target_lang}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                return escape_markdown_v2(data['responseData']['translatedText'])  # Экранируем результат
        except aiohttp.ClientError as e:
            return escape_markdown_v2(f"Ошибка перевода: {e}")

async def get_joke():
    """Получение случайной шутки."""
    url = "https://official-joke-api.appspot.com/random_joke"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                return escape_markdown_v2(f"{data['setup']}\n\n{data['punchline']}")  # Экранируем шутку
        except aiohttp.ClientError as e:
            return escape_markdown_v2(f"Ошибка при загрузке шутки: {e}")

@dp.message(Command('start'))
async def start_command(message: Message):
    """Обработка команды /start."""
    await message.answer(
        escape_markdown_v2(
            "Привет! Я твой умный ассистент. Вот что я умею:\n"
            "/weather <город> — Показать погоду\n"
            "/motivation — Мотивационная фраза\n"
            "/movie — Рекомендация фильма\n"
            "/image <запрос> <кол-во> — Поиск изображений высокого качества\n"
            "/ask <вопрос> — Ответ на вопрос с помощью ИИ\n"
            "/translate <текст> — Перевод текста (ru/en)\n"
            "/joke — Случайная шутка\n"
            "Пример: `/image закат 3`, `/ask Что такое солнце?`"
        ),
        parse_mode=PARSE_MODE
    )

@dp.message(Command('weather'))
async def weather_command(message: Message):
    """Получение погоды для указанного города."""
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(escape_markdown_v2("Укажите город! Пример: /weather Москва"), parse_mode=PARSE_MODE)
            return
        city = args[1]
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://wttr.in/{requests.utils.quote(city)}?format=3") as response:
                response.raise_for_status()
                weather_text = await response.text()
                await message.answer(escape_markdown_v2(weather_text), parse_mode=PARSE_MODE)
    except aiohttp.ClientError as e:
        await message.answer(escape_markdown_v2(f"Не удалось получить погоду: {e}. Пример: /weather Москва"), parse_mode=PARSE_MODE)

@dp.message(Command("movie"))
async def recommend_movie(message: Message):
    """Рекомендация случайного фильма."""
    try:
        movies = get_movies()
        if not movies:
            await message.reply(escape_markdown_v2("Не удалось найти фильмы. Попробуйте позже."), parse_mode=PARSE_MODE)
            return
        title, description = random.choice(movies)
        escaped_title = escape_markdown_v2(title)
        escaped_description = escape_markdown_v2(description)
        await message.reply(
            f"Сегодня рекомендую: *{escaped_title}*\n\nОписание: {escaped_description}",
            parse_mode=PARSE_MODE
        )
    except Exception as e:
        await message.reply(escape_markdown_v2(f"Ошибка: {e}"), parse_mode=PARSE_MODE)

@dp.message(Command("motivation"))
async def motivation_command(message: Message):
    """Отправка случайной мотивационной фразы."""
    try:
        quotes = get_motivation()
        quote = random.choice(quotes)
        escaped_quote = escape_markdown_v2(quote)
        await message.reply(f"*{escaped_quote}*", parse_mode=PARSE_MODE)
    except Exception as e:
        await message.reply(escape_markdown_v2(f"Ошибка: {e}"), parse_mode=PARSE_MODE)

@dp.message(Command('image'))
async def image_command(message: Message):
    """Поиск и отправка изображений высокого качества."""
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(escape_markdown_v2("Укажите запрос и количество! Пример: /image закат 3"), parse_mode=PARSE_MODE)
            return
        parts = args[1].rsplit(maxsplit=1)
        if len(parts) < 2 or not parts[1].isdigit():
            await message.answer(escape_markdown_v2("Укажите запрос и число! Пример: /image закат 3"), parse_mode=PARSE_MODE)
            return
        query, num_images = parts[0], int(parts[1])
        if num_images > 10:
            await message.answer(escape_markdown_v2("Максимум 10 изображений!"), parse_mode=PARSE_MODE)
            return
        
        await message.answer(escape_markdown_v2(f"Ищу {num_images} изображений по запросу '{query}'..."), parse_mode=PARSE_MODE)
        image_paths, temp_dir = await search_and_download_images(query, num_images)
        
        if image_paths:
            for img_path in image_paths:
                input_file = FSInputFile(img_path)
                await bot.send_photo(message.chat.id, input_file)
            await message.answer(escape_markdown_v2(f"Отправлено {len(image_paths)} изображений по запросу '{query}'."), parse_mode=PARSE_MODE)
        else:
            await message.answer(escape_markdown_v2("Не удалось найти изображения."), parse_mode=PARSE_MODE)
        
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    except ValueError:
        await message.answer(escape_markdown_v2("Количество должно быть числом! Пример: /image закат 3"), parse_mode=PARSE_MODE)
    except Exception as e:
        await message.answer(escape_markdown_v2(f"Ошибка: {e}. Пример: /image закат 3"), parse_mode=PARSE_MODE)

@dp.message(Command('ask'))
async def ask_command(message: Message):
    """Ответ на вопрос с использованием нейросети."""
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(escape_markdown_v2("Задайте вопрос! Пример: /ask Что такое солнце?"), parse_mode=PARSE_MODE)
            return
        question = args[1]
        context = "Солнце — это звезда в центре Солнечной системы."
        result = nlp(question=question, context=context)
        answer = escape_markdown_v2(result['answer'])
        await message.reply(f"Ответ: *{answer}* \\(уверенность: {result['score']:.2f}\\)", parse_mode=PARSE_MODE)
    except Exception as e:
        await message.reply(escape_markdown_v2(f"Ошибка: {e}. Пример: /ask Что такое солнце?"), parse_mode=PARSE_MODE)

@dp.message(Command('translate'))
async def translate_command(message: Message):
    """Перевод текста."""
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(escape_markdown_v2("Укажите текст! Пример: /translate Привет"), parse_mode=PARSE_MODE)
            return
        text = args[1]
        translated = await translate_text(text, target_lang="en" if text[0].isalpha() and text[0].isascii() else "ru")
        await message.reply(f"Перевод: *{translated}*", parse_mode=PARSE_MODE)
    except Exception as e:
        await message.reply(escape_markdown_v2(f"Ошибка: {e}. Пример: /translate Привет"), parse_mode=PARSE_MODE)

@dp.message(Command('joke'))
async def joke_command(message: Message):
    """Отправка случайной шутки."""
    try:
        joke = await get_joke()
        await message.reply(joke, parse_mode=PARSE_MODE)
    except Exception as e:
        await message.reply(escape_markdown_v2(f"Ошибка: {e}"), parse_mode=PARSE_MODE)

@dp.startup()
async def on_startup():
    """Сообщение при запуске бота."""
    print("Бот запущен")

async def main():
    """Основная функция запуска бота."""
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
