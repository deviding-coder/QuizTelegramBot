import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
import aiosqlite
from aiogram import F
import xml.etree.ElementTree as ET

# сделать: get_statistics возвращает полную статистику


# включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)

# парсинг файла с api токеном и именами файлов баз данных с помощью xml.etree.ElementTree
tree = ET.parse('data/info.xml')
root = tree.getroot()

# читаем информацию из info.xml
API_TOKEN = root[0].text
DB_NAME = root[1].text
QUESTION_DB_NAME = root[2].text

# объект бота
bot = Bot(token=API_TOKEN)
# диспетчер
dp = Dispatcher()


# вход: идентификатор вопроса
# выход: кортеж (текст_вопроса, вариант1, вариант2, вариант3, вариант4, правильный_вариант)
async def get_question_and_options(question_id):
    async with aiosqlite.connect(QUESTION_DB_NAME) as db:
        async with db.execute('SELECT question_text, option1, option2, option3, option4, correct_option FROM questions WHERE quest_id = (?)', (question_id + 1, )) as cursor:
            results = await cursor.fetchone()
            return results

# выход: число записей в таблице questions в бд QUESTION_DB_NAME
async def get_question_amount():
    async with aiosqlite.connect(QUESTION_DB_NAME) as db:
        async with db.execute('SELECT count(*) FROM questions') as cursor:
            result = await cursor.fetchone()
            return result[0]

# вход: идентификатор пользователя
# выход: последний записанный результат
async def get_last_result(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT last_result FROM quiz_state WHERE user_id = (?)', (user_id, )) as cursor:
            last_result = await cursor.fetchone()
            if last_result is not None:
                return last_result[0]
            else:
                return 0


# ф: создает кнопки вариантов ответа
# вход: массив_вариантов, правильный вариант
# выход: сконструированный InlineKeyboardMarkup
def generate_options_keyboard(answer_options, right_answer):
    builder = InlineKeyboardBuilder()
    for option in answer_options:
        builder.add(types.InlineKeyboardButton(
            text=option,
            # ответ верный - колбэк-запрос 'right_answer'
            # ответ неверный - колбэк-запрос 'wrong_answer'
            callback_data="right_answer" if option == right_answer else "wrong_answer")
        )
    builder.adjust(1)
    return builder.as_markup()


# ф: отправка сообщения с вопросом и вариантами ответа
# вход: сообщение, индентификатор_пользователя
# выход: нет
async def get_question(message, user_id):
    current_question_index = await get_quiz_index(user_id)
    question_info = await get_question_and_options(current_question_index)
    # получаем правильный ответ для текущего вопроса
    correct_opt = question_info[5]
    # получаем список вариантов ответа для текущего вопроса
    opts = question_info[1:5]
    kb = generate_options_keyboard(opts, correct_opt)
    # отправляем в чат сообщение с вопросом, прикрепляем сгенерированные кнопки
    await message.answer(f"{question_info[0]}", reply_markup=kb)

# ф: создание таблицы quiz_state в бд DB_NAME
# выход: нет
async def create_table():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS quiz_state (user_id INTEGER PRIMARY KEY, question_index INTEGER, last_result INTEGER)''')
        await db.commit()

# ф: обновить информацию в таблице quiz_state бд DB_NAME
# вход: идентификатор_пользователя, индекс_текущего_вопроса, ответ
# выход: нет
async def update_quiz_index(user_id, index, answer):
    async with aiosqlite.connect(DB_NAME) as db:
        # если параметр answer равен 0 - новый квиз
        if answer == 0:
            await db.execute('INSERT OR REPLACE INTO quiz_state (user_id, question_index, last_result) VALUES (?, ?, ?)', (user_id, index, answer, ))
        else:
            last_result = await get_last_result(user_id)
            # если параметр answer равен correct - ответ на вопрос верный
            if answer == 'correct':
                last_result += 1
            await db.execute('INSERT OR REPLACE INTO quiz_state (user_id, question_index, last_result) VALUES (?, ?, ?)', (user_id, index, last_result, ))
        await db.commit()

# ф: получить индекс вопроса, на котором остановился пользователь
# вход: идентификатор пользователя
# выход: индекс вопроса, если пользователь есть в таблице, иначе 0
async def get_quiz_index(user_id):
     async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT question_index FROM quiz_state WHERE user_id = (?)', (user_id, )) as cursor:
            results = await cursor.fetchone()
            if results is not None:
                return results[0]
            else:
                return 0

# ф: начать квиз заново
# вход: сообщение
# выход: нет
async def new_quiz(message):
    user_id = message.from_user.id
    # сбрасываем значение текущего индекса вопроса квиза в 0
    current_question_index = 0

    await update_quiz_index(user_id, current_question_index, 0)
    # запрашиваем новый вопрос для квиза
    await get_question(message, user_id)

# ф: возвращает 
# выход: текст из количество_вопросов строк "X человек ответил(и) на Y вопрос(ов)"
async def get_statistics():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT last_result, COUNT(last_result) FROM quiz_state GROUP BY last_result  ORDER BY last_result ') as cursor:
            results = await cursor.fetchall()
    res_dict = dict(results)
    for i in range(11):
        if i not in res_dict:
            res_dict[i] = 0
    res_list = list(res_dict.items())
    res_list.sort()
    result = tuple(res_list)
    final_result = ''
    question_amount = get_question_amount()
    for stat_tuple in result:
        final_result += f'{stat_tuple[1]} человек ответил(и) на {stat_tuple[0]} вопрос(ов)' + ('\n' if stat_tuple[0] != question_amount else '')
    return final_result

# Хэндлер на команду /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="Начать игру"))
    builder.add(types.KeyboardButton(text="Статистика"))
    await message.answer("Добро пожаловать в квиз!", reply_markup=builder.as_markup(resize_keyboard=True))

# Хэндлер на команду /statistics
@dp.message(F.text=="Статистика")
@dp.message(Command("statistics"))
async def cmd_statistics(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="Начать игру"))
    builder.add(types.KeyboardButton(text="Статистика"))
    statistic_answer = await get_statistics()
    await message.answer(f"Статистика: \n{statistic_answer}", reply_markup=builder.as_markup(resize_keyboard=True))

# Хэндлер на команды /quiz
@dp.message(F.text=="Начать игру")
@dp.message(Command("quiz"))
async def cmd_quiz(message: types.Message):
    await message.answer(f"Давайте начнем квиз!")
    await new_quiz(message)

# ф: получить правильность ответа, вывести следующий вопрос или окончить квиз
# вход: колбэк-запрос правильного ответа
# выход: нет
@dp.callback_query(F.data == "right_answer")
async def right_answer(callback: types.CallbackQuery):
    # редактируем текущее сообщение с целью убрать кнопки (reply_markup=None)
    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )
    current_question_index = await get_quiz_index(callback.from_user.id)
    question_info = await get_question_and_options(current_question_index)
    correct_option = question_info[5]
    await callback.message.answer(f"Верно! {correct_option}")

    # обновление номера текущего вопроса в базе данных
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index, 'correct')

    question_amount = await get_question_amount()
    # проверяем достигнут ли конец квиза
    if current_question_index < question_amount:
        # следующий вопрос
        await get_question(callback.message, callback.from_user.id)
    else:
        last_result = await get_last_result(callback.from_user.id)
        # уведомление об окончании квиза, показ числа верных ответов от общего количества
        await callback.message.answer(f"Это был последний вопрос. Квиз завершен! Ваш результат: {last_result}/{question_amount}")

# ф: получить правильность ответа, вывести следующий вопрос или окончить квиз
# вход: колбэк-запрос неправильного ответа
# выход: нет
@dp.callback_query(F.data == "wrong_answer")
async def wrong_answer(callback: types.CallbackQuery):
    # редактируем текущее сообщение с целью убрать кнопки (reply_markup=None)
    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )
    current_question_index = await get_quiz_index(callback.from_user.id)
    question_info = await get_question_and_options(current_question_index)
    correct_option = question_info[5]

    # отправляем в чат сообщение об ошибке с указанием верного ответа
    await callback.message.answer(f"Неправильно. \n✔Ваш ответ: {correct_option}. \n❌Правильный ответ: {correct_option}")

    # обновление номера текущего вопроса в базе данных
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index, 'wrong')

    question_amount = await get_question_amount()
    # проверяем достигнут ли конец квиза
    if current_question_index < question_amount:
        # следующий вопрос
        await get_question(callback.message, callback.from_user.id)
    else:
        # уведомление об окончании квиза, показ числа верных ответов от общего количества
        last_result = await get_last_result(callback.from_user.id)
        await callback.message.answer(f"Это был последний вопрос. Квиз завершен! Ваш результат: {last_result}/{question_amount}")

# запуск процесса поллинга новых апдейтов
async def main():
    await create_table()
    await dp.start_polling(bot)

if __name__ == "__main__":
    
    asyncio.run(main())