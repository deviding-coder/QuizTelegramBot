import xml.etree.ElementTree as ET
import aiosqlite

tree = ET.parse('data/info.xml')
root = tree.getroot()

DB_NAME = root[1].text
QUESTION_DB_NAME = root[2].text

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

