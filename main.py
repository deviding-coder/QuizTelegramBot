import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
import aiosqlite
from aiogram import F
import xml.etree.ElementTree as ET


# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)
tree = ET.parse('data/info.xml')
root = tree.getroot()
# Замените "YOUR_BOT_TOKEN" на токен, который вы получили от BotFather
API_TOKEN = root[0].text


# Объект бота
bot = Bot(token=API_TOKEN)
# Диспетчер
dp = Dispatcher()

DB_NAME = root[1].text
QUESTION_DB_NAME = root[2].text

async def get_question_and_options(question_id):
    async with aiosqlite.connect(QUESTION_DB_NAME) as db:
        async with db.execute('SELECT question_text, option1, option2, option3, option4, correct_option FROM questions WHERE quest_id = (?)', (question_id + 1, )) as cursor:
            # Возвращаем результат
            results = await cursor.fetchone()
            return results

async def get_question_amount():
    async with aiosqlite.connect(QUESTION_DB_NAME) as db:
        async with db.execute('SELECT count(*) FROM questions') as cursor:
            # Возвращаем результат
            result = await cursor.fetchone()
            return result[0]

async def get_last_result(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT last_result FROM quiz_state WHERE user_id = (?)', (user_id, )) as cursor:
            last_result = await cursor.fetchone()
            if last_result is not None:
                return last_result[0]
            else:
                return 0

def generate_options_keyboard(answer_options, right_answer):
  # Создаем сборщика клавиатур типа Inline
    builder = InlineKeyboardBuilder()

    # В цикле создаем 4 Inline кнопки, а точнее Callback-кнопки
    for option in answer_options:
        builder.add(types.InlineKeyboardButton(
            # Текст на кнопках соответствует вариантам ответов
            text=option,
            # Присваиваем данные для колбэк запроса.
            # Если ответ верный сформируется колбэк-запрос с данными 'right_answer'
            # Если ответ неверный сформируется колбэк-запрос с данными 'wrong_answer'
            callback_data="right_answer" if option == right_answer else "wrong_answer")
        )

    # Выводим по одной кнопке в столбик
    builder.adjust(1)
    return builder.as_markup()

async def get_question(message, user_id):

    # Запрашиваем из базы текущий индекс для вопроса
    current_question_index = await get_quiz_index(user_id)
    question_info = await get_question_and_options(current_question_index)
    # Получаем правильный ответ для текущего вопроса
    correct_opt = question_info[5]
    # Получаем список вариантов ответа для текущего вопроса
    opts = question_info[1:5]

    # Функция генерации кнопок для текущего вопроса квиза
    # В качестве аргументов передаем варианты ответов и значение правильного ответа
    kb = generate_options_keyboard(opts, correct_opt)
    # Отправляем в чат сообщение с вопросом, прикрепляем сгенерированные кнопки
    await message.answer(f"{question_info[0]}", reply_markup=kb)

async def create_table():
    # Создаем соединение с базой данных (если она не существует, то она будет создана)
    async with aiosqlite.connect(DB_NAME) as db:
        # Выполняем SQL-запрос к базе данных
        await db.execute('''CREATE TABLE IF NOT EXISTS quiz_state (user_id INTEGER PRIMARY KEY, question_index INTEGER, last_result INTEGER)''')
        # Сохраняем изменения
        await db.commit()

async def update_quiz_index(user_id, index, answer):
    # Создаем соединение с базой данных (если она не существует, она будет создана)
    async with aiosqlite.connect(DB_NAME) as db:
        # Вставляем новую запись или заменяем ее, если с данным user_id уже существует
        if answer == 0:
            await db.execute('INSERT OR REPLACE INTO quiz_state (user_id, question_index, last_result) VALUES (?, ?, ?)', (user_id, index, answer, ))
        else:
            last_result = await get_last_result(user_id)
            if answer == 'correct':
                last_result += 1
            await db.execute('INSERT OR REPLACE INTO quiz_state (user_id, question_index, last_result) VALUES (?, ?, ?)', (user_id, index, last_result, ))
        # Сохраняем изменения
        await db.commit()

async def get_quiz_index(user_id):
     # Подключаемся к базе данных
     async with aiosqlite.connect(DB_NAME) as db:
        # Получаем запись для заданного пользователя
        async with db.execute('SELECT question_index FROM quiz_state WHERE user_id = (?)', (user_id, )) as cursor:
            # Возвращаем результат
            results = await cursor.fetchone()
            if results is not None:
                return results[0]
            else:
                return 0

async def new_quiz(message):
    # получаем id пользователя, отправившего сообщение
    user_id = message.from_user.id
    # сбрасываем значение текущего индекса вопроса квиза в 0
    current_question_index = 0
    await update_quiz_index(user_id, current_question_index, 0)

    # запрашиваем новый вопрос для квиза
    await get_question(message, user_id)


# Хэндлер на команду /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Создаем сборщика клавиатур типа Reply
    builder = ReplyKeyboardBuilder()
    # Добавляем в сборщик одну кнопку
    builder.add(types.KeyboardButton(text="Начать игру"))
    # Прикрепляем кнопки к сообщению
    await message.answer("Добро пожаловать в квиз!", reply_markup=builder.as_markup(resize_keyboard=True))

# Хэндлер на команды /quiz
@dp.message(F.text=="Начать игру")
@dp.message(Command("quiz"))
async def cmd_quiz(message: types.Message):
    # Отправляем новое сообщение без кнопок
    await message.answer(f"Давайте начнем квиз!")
    # Запускаем новый квиз
    await new_quiz(message)


@dp.callback_query(F.data == "right_answer")
async def right_answer(callback: types.CallbackQuery):
    # редактируем текущее сообщение с целью убрать кнопки (reply_markup=None)
    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )

    # Получение текущего вопроса для данного пользователя
    current_question_index = await get_quiz_index(callback.from_user.id)

    # Отправляем в чат сообщение, что ответ верный
    await callback.message.answer("Верно!")

    # Обновление номера текущего вопроса в базе данных
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index, 'correct')
    question_amount = await get_question_amount()

    # Проверяем достигнут ли конец квиза
    if current_question_index < question_amount:
        # Следующий вопрос
        await get_question(callback.message, callback.from_user.id)
    else:
        last_result = await get_last_result(callback.from_user.id)
        # Уведомление об окончании квиза
        await callback.message.answer(f"Это был последний вопрос. Квиз завершен! Ваш результат: {last_result}/{question_amount}")

@dp.callback_query(F.data == "wrong_answer")
async def wrong_answer(callback: types.CallbackQuery):
    # редактируем текущее сообщение с целью убрать кнопки (reply_markup=None)
    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )

    # Получение текущего вопроса для данного пользователя
    current_question_index = await get_quiz_index(callback.from_user.id)

    question_info = await get_question_and_options(current_question_index)
    # Получаем правильный ответ для текущего вопроса

    correct_option = question_info[5]

    # Отправляем в чат сообщение об ошибке с указанием верного ответа
    await callback.message.answer(f"Неправильно. Правильный ответ: {correct_option}")

    # Обновление номера текущего вопроса в базе данных
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index, 'wrong')
    question_amount = await get_question_amount()

    # Проверяем достигнут ли конец квиза
    if current_question_index < question_amount:
        # Следующий вопрос
        await get_question(callback.message, callback.from_user.id)
    else:
        # Уведомление об окончании квиза
        last_result = await get_last_result(callback.from_user.id)
        await callback.message.answer(f"Это был последний вопрос. Квиз завершен! Ваш результат: {last_result}/{question_amount}")

# Запуск процесса поллинга новых апдейтов
async def main():
    await create_table()
    await dp.start_polling(bot)

if __name__ == "__main__":
    
    asyncio.run(main())