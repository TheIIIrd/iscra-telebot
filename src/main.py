"""
Технически, это должен быть бот Telegram для быстрого доступа к полезной информации от ISCRA.
Он может:
- Собирать данные, введённые в сообщении
- Проверять корректность введения (условно формат даты, группы, ФИО)
- Давать возможность выбора категории, после чего выдавать информационное сообщение
- Сохранять человека в базу данных (при этом сохранять то, на что он нажал в процессе регистрации)
"""

import asyncio  # Для асинхронного выполнения
import re  # Для работы с регулярными выражениями
from typing import List  # Импортируем List для аннотации

from asyncpg import connect
from telebot.async_telebot import AsyncTeleBot, types
from telebot.asyncio_filters import StateFilter
from telebot.handler_backends import State, StatesGroup
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Замените <token> на ваш токен бота
TOKEN = "<token>"

mentor_table = {
    370880482: ["Артур", 1],
    203344707: ["Влад", 2],
    543439074: ["Алексей", 3],
    668188357: ["Дмитрий", 4],
    439665802: ["Даниил", 5],
    54799591: ["Мариам", 6],
    2119560016: ["Антон", 7]

}

# Создаем асинхронного бота
bot = AsyncTeleBot(TOKEN)

# Словарь для хранения данных пользователей до их сохранения в базу данных
user_data = {}

DB_CONFIG = {
    "host": "localhost",  # Замените на ваш хост
    "port": 5432,  # Порт по умолчанию для PostgreSQL
    "user": "postgres",  # Замените на ваше имя пользователя
    "password": "root",  # Замените на ваш пароль
    "database": "postgres",  # Замените на вашу базу данных
}

# Регистрируем фильтр состояний для обработки состояния пользователей
bot.add_custom_filter(StateFilter(bot))


class UserStates(StatesGroup):
    """
    Определяет состояния пользователя при взаимодействии с ботом.
    """
    # Состояния для ввода информации
    full_name = State()  # Ввод полного имени
    group_name = State()  # Ввод названия группы
    topic = State()  # Ввод темы
    subtopic = State()  # Ввод подтемы
    additional_info = State()  # Ввод дополнительной информации
    mentor = State()  # Ввод имени наставника
    check = State()  # Проверка введенной информации

    # Состояния для редактирования информации
    edit_name = State()  # Редактирование полного имени
    edit_group = State()  # Редактирование названия группы
    edit_topic = State()  # Редактирование темы
    edit_subtopic = State()  # Редактирование подтемы
    edit_additional_info = State()  # Редактирование дополнительной информации
    edit_mentor = State()  # Редактирование имени наставника

    edit_name_2 = State()  # Редактирование полного имени
    edit_group_2 = State()  # Редактирование названия группы
    edit_topic_2 = State()  # Редактирование темы
    edit_subtopic_2 = State()  # Редактирование подтемы
    edit_additional_info_2 = State()  # Редактирование дополнительной информации
    edit_mentor_2 = State()  # Редактирование имени наставника

    # Состояния для промежуточных этапов
    registered = State()  # Пользователь зарегистрирован
    not_registered = State()  # Пользователь не зарегистрирован
    deleting = State()  # Состояние удаления заявки
    editing = State()  # Состояние редактирования заявки
    Zhurin = State()


# Получаем список тем из базы данных
async def get_topics(conn):
    return await conn.fetch("SELECT id, full_name FROM topics")


# Получаем список менторов по теме
async def get_mentors_by_topic(conn, mentor_ids):
    return await conn.fetch("""
        SELECT id, full_name
        FROM mentors
        WHERE id = ANY($1)
        AND registered < max_registered
    """, mentor_ids)


# Получаем список подтем у ментора
async def get_subtopics_by_mentor(conn, subtopic_id):
    return await conn.fetch("SELECT id, full_name FROM subtopics WHERE id = ANY($1) AND NOT picked", subtopic_id)


async def topics_keyboard(conn, param=0):
    topics = await get_topics(conn)
    keyboard = InlineKeyboardMarkup(row_width=2)
    if param == 42:
        for topic in topics:
            topic_button = InlineKeyboardButton(
                text=topic['full_name'],
                callback_data=f'infotopic_{topic["id"]}'
            )
            keyboard.add(topic_button)
    else:
        for topic in topics:
            topic_button = InlineKeyboardButton(
                text=topic['full_name'],
                callback_data=f'topic_{topic["id"]}'
            )
            keyboard.add(topic_button)
    return keyboard


# Создаем клавиатуру для менторов с кнопкой "Назад"
async def mentors_keyboard(conn, topic_id, param=0):
    mentor_ids = await conn.fetch("SELECT mentor FROM topics WHERE id = $1", topic_id)
    mentors = await get_mentors_by_topic(conn, mentor_ids)
    keyboard = InlineKeyboardMarkup(row_width=2)
    if param == 42:
        for mentor in mentors:
            mentor_button = InlineKeyboardButton(
                text=mentor['full_name'],
                callback_data=f'infomentor_{mentor["id"]}'
            )
            keyboard.add(mentor_button)
    else:
        for mentor in mentors:
            mentor_button = InlineKeyboardButton(
                text=mentor['full_name'],
                callback_data=f'mentor_{mentor["id"]}'
            )
            keyboard.add(mentor_button)

    return keyboard


# Создаем клавиатуру для подтем с кнопкой "Назад"
async def subtopics_keyboard(conn, mentor_id, param=0):
    subtopic_id = await conn.fetch("SELECT subtopic FROM mentors WHERE id = $1", mentor_id)
    subtopics = await get_subtopics_by_mentor(conn, subtopic_id)
    keyboard = InlineKeyboardMarkup(row_width=2)
    if param == 42:
        for subtopic in subtopics:
            subtopic_button = InlineKeyboardButton(
                text=subtopic['full_name'],
                callback_data=f'infosubtopic_{subtopic["id"]}'
            )
            keyboard.add(subtopic_button)
    else:
        for subtopic in subtopics:
            subtopic_button = InlineKeyboardButton(
                text=subtopic['full_name'],
                callback_data=f'subtopic_{subtopic["id"]}'
            )
            keyboard.add(subtopic_button)

    return keyboard


# Начало процесса, выбор темы
async def start_add_user(message):
    conn = await connect(**DB_CONFIG)
    user_id = message.from_user.id
    user_data[user_id] = {}  # Инициализируем словарь для пользователя
    await bot.send_message(message.chat.id, "Приступим к регистрации", reply_markup=types.ReplyKeyboardRemove())
    keyboard = await topics_keyboard(conn)
    keyboard.add(InlineKeyboardButton(text="Назад", callback_data='start'))
    await bot.send_message(message.chat.id, "Выберите тему:", reply_markup=keyboard)
    await conn.close()


# Обработка выбора темы
@bot.callback_query_handler(func=lambda c: c.data.startswith('topic_'))
async def process_topic(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    topic_id = int(callback_query.data.split('_')[1])

    # Сохраняем выбор темы в user_data
    user_data[user_id]['topic_id'] = topic_id

    conn = await connect(**DB_CONFIG)
    keyboard = await mentors_keyboard(conn, topic_id)
    back_button = InlineKeyboardButton(text="Назад", callback_data='back_to_topics')
    keyboard.add(back_button)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.send_message(callback_query.message.chat.id, "Выберите ментора:", reply_markup=keyboard)
    await conn.close()


# Обработка выбора ментора
@bot.callback_query_handler(func=lambda c: c.data.startswith('mentor_'))
async def process_mentor(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    mentor_id = int(callback_query.data.split('_')[1])
    if mentor_id == 3:
        keyboard = InlineKeyboardMarkup(InlineKeyboardButton(text="Назад", callback_data='back_to_mentors'))
        await bot.send_message(callback_query.message.chat.id,
                               "Алексей Журин принимает студентов по предварительной проверке. Свяжитесь с ним для подробной информации:",
                               reply_markup=keyboard)
        await bot.forward_message(callback_query.message.chat.id, -1002325501843, 18)
        await bot.send_message(callback_query.message.chat.id, "Введите пароль:\n", reply_markup=keyboard)
        await bot.set_state(user_id, UserStates.Zhurin, user_id)
    # Сохраняем выбор ментора в user_data
    else:
        user_data[user_id]['mentor_id'] = mentor_id

        conn = await connect(**DB_CONFIG)
        keyboard = await subtopics_keyboard(conn, mentor_id)
        back_button = InlineKeyboardButton(text="Назад", callback_data='back_to_mentors')
        keyboard.add(back_button)
        await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
        await bot.send_message(callback_query.message.chat.id, "Выберите подтему:", reply_markup=keyboard)
        await conn.close()


@bot.message_handler(state=UserStates.Zhurin)
async def password_check(message):
    if message.text == "".join(map(chr,
                                   [73, 85, 56, 32, 45, 32, 108, 117, 99, 104, 115, 104, 97, 121, 97, 32, 107, 97, 102,
                                    101, 100, 114, 97, 32, 110, 97, 32, 115, 118, 101, 116, 101])):
        await bot.send_message(message.chat.id, "Пароль верный")
        mentor_id = 3
        user_data[message.from_user.id]['mentor_id'] = mentor_id

        conn = await connect(**DB_CONFIG)
        keyboard = await subtopics_keyboard(conn, mentor_id)
        back_button = InlineKeyboardButton(text="Назад", callback_data='back_to_mentors')
        keyboard.add(back_button)
        await bot.delete_message(message.chat.id, message.id)
        await bot.send_message(message.chat.id, "Выберите подтему:", reply_markup=keyboard)
        await conn.close()
    else:
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(InlineKeyboardButton(text="Назад", callback_data='back_to_mentors'))
        await bot.send_message(message.chat.id, "Пароль неверный, попробуйте вновь", reply_markup=keyboard)


# Обработка выбора подтемы
@bot.callback_query_handler(func=lambda c: c.data.startswith('subtopic_'))
async def process_subtopic(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    subtopic = int(callback_query.data.split('_')[1])
    # Сохраняем выбор подтемы в user_data
    user_data[user_id]['subtopic_id'] = subtopic
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton(text="Назад", callback_data='back_to_subtopic'))
    current_state = await bot.get_state(user_id, callback_query.message.chat.id)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    if current_state in [UserStates.edit_topic.name, UserStates.edit_mentor.name, UserStates.subtopic.name]:
        await bot.send_message(callback_query.message.chat.id, "Данные успешно изменены")
        await back_to_check(callback_query)
    else:
        await bot.set_state(callback_query.from_user.id, UserStates.full_name, callback_query.message.chat.id)
        await bot.send_message(callback_query.message.chat.id, f"Введите ваше ФИО:", reply_markup=keyboard)


# Эта функция обрабатывает вход имени от пользователя
@bot.message_handler(state=UserStates.full_name)
async def get_full_name(message):
    """
    Обрабатывает ввод ФИО от пользователя.
    Проверяет на корректность введенных данных и переходит к следующему состоянию.

    :param message: Объект сообщения от пользователя
    """

    user_id = message.from_user.id
    # Фильтр на текст и символ - при двойной фамилии
    russian_letter_regex = r"^[А-Яа-яёЁ\s\-]+$"
    if bool(re.match(russian_letter_regex, message.text)):
        # Сохраняем ФИО в память
        user_data[user_id]["full_name"] = message.text
        await bot.set_state(user_id, UserStates.group_name, message.chat.id)
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(InlineKeyboardButton(text="Назад", callback_data='back_to_fio'))
        await bot.reply_to(message, "Введите вашу группу:", reply_markup=keyboard)

    else:
        await bot.reply_to(
            message, "Вы использовали недопустимые символы. Попробуйте вновь:"
        )


# Эта функция обрабатывает ввод названия группы от пользователя
@bot.message_handler(state=UserStates.group_name)
async def get_group_name(message):
    """
    Обрабатывает ввод названия группы от пользователя.
    Проверяет корректность введенных данных и переходит к следующему состоянию.

    :param message: Объект сообщения от пользователя
    """

    user_id = message.from_user.id
    # Фильтр на правильный формат группы
    format_regex = r"^[А-Яа-яёЁ]{2}\d-\d{2}$"
    if bool(re.match(format_regex, message.text)):
        user_data[user_id]["group_name"] = message.text
        await bot.set_state(user_id, UserStates.additional_info, message.chat.id)
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(InlineKeyboardButton(text="Назад", callback_data='back_to_group'))
        await bot.reply_to(message, "Введите дополнительную информацию (или пропустите, отправив '-'):",
                           reply_markup=keyboard)

    else:
        await bot.reply_to(
            message, "Вы использовали недопустимые символы. Попробуйте вновь:"
        )


# Эта функция обрабатывает ввод дополнительной информации от пользователя
@bot.message_handler(state=UserStates.additional_info)
async def get_additional_info(message):
    """
    Обрабатывает ввод дополнительной информации от пользователя.
    Проверяет состояние и сохраняет информацию, если она введена корректно.

    :param message: Объект сообщения от пользователя
    """
    conn = await connect(**DB_CONFIG)
    user_id = message.from_user.id
    # Сохраняем дополнительную информацию или устанавливаем None, если пользователь ввел '-'
    user_data[user_id]["additional_info"] = (
        message.text if message.text != "-" else None
    )
    response = (
        f"ФИО: {user_data[user_id]['full_name']}\n"
        f"Группа: {user_data[user_id]['group_name']}\n"
        f"Тема: {await conn.fetchval('SELECT full_name FROM topics WHERE id = $1', user_data[user_id].get('topic_id'))}\n"
        f"Ментор: {await conn.fetchval('SELECT full_name FROM mentors WHERE id = $1', user_data[user_id].get('mentor_id'))}\n"
        f"Подтема: {await conn.fetchval('SELECT full_name FROM subtopics WHERE id = $1', user_data[user_id]['subtopic_id'])}\n"
        f"Доп. информация: {user_data[user_id]['additional_info']}\n"
    )
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton(text="Да", callback_data='correct_info'))
    keyboard.add(InlineKeyboardButton(text="Нет", callback_data='edit_info'))
    await bot.send_message(
        message.chat.id, f"Проверь, верно ли всё:\n {response}", reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda c: c.data == 'start')
async def starter(callback_query: types.CallbackQuery):
    try:
        user_data.pop(
            callback_query.from_user.id, None
        )
    except Exception as e:
        print(
            f"Error deleting user data: {e}"
        )
    await bot.set_state(
        callback_query.from_user.id, UserStates.not_registered, callback_query.message.chat.id
    )
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    markup = await create_keyboard(
        [
            "Поддержка",
            "Регистрация",
            "Узнать темы",
            "Назад",
        ]
    )
    await bot.send_message(
        callback_query.message.chat.id,
        f"Привет, {callback_query.from_user.first_name}! Что ты хочешь сделать?",
        reply_markup=markup,
    )


# Обработка нажатия кнопки "Назад" для возврата к выбору тем
@bot.callback_query_handler(func=lambda c: c.data == 'back_to_topics')
async def back_to_topics(callback_query: types.CallbackQuery):
    conn = await connect(**DB_CONFIG)
    keyboard = await topics_keyboard(conn)
    keyboard.add(InlineKeyboardButton(text="Назад", callback_data='start'))
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.send_message(callback_query.message.chat.id, "Выберите тему:", reply_markup=keyboard)
    await conn.close()


# Обработка нажатия кнопки "Назад" для возврата к выбору менторов
@bot.callback_query_handler(func=lambda c: c.data == 'back_to_mentors')
async def back_to_mentors(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    await bot.set_state(user_id, UserStates.not_registered, user_id)
    topic_id = user_data[user_id].get('topic_id')

    conn = await connect(**DB_CONFIG)
    keyboard = await mentors_keyboard(conn, topic_id)
    back_button = InlineKeyboardButton(text="Назад", callback_data='back_to_topics')
    keyboard.add(back_button)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.send_message(callback_query.message.chat.id, "Выберите ментора:", reply_markup=keyboard)
    await conn.close()


@bot.callback_query_handler(func=lambda c: c.data == 'back_to_subtopic')
async def back_to_subtopic(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    conn = await connect(**DB_CONFIG)
    keyboard = await subtopics_keyboard(conn, user_data[user_id].get('mentor_id'))
    back_button = InlineKeyboardButton(text="Назад", callback_data='back_to_mentors')
    keyboard.add(back_button)
    await bot.delete_state(user_id, callback_query.message.chat.id)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.send_message(callback_query.message.chat.id, "Выберите подтему:", reply_markup=keyboard)
    await conn.close()


@bot.callback_query_handler(func=lambda c: c.data == 'back_to_fio')
async def back_to_fio(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Назад", callback_data="back_to_subtopic"))
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.set_state(user_id, UserStates.full_name, callback_query.message.chat.id)
    await bot.send_message(callback_query.message.chat.id, "Введите ваше ФИО:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda c: c.data == 'back_to_group')
async def back_to_group(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Назад", callback_data="back_to_fio"))
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.set_state(user_id, UserStates.group_name, callback_query.message.chat.id)
    await bot.send_message(callback_query.message.chat.id, "Введите вашу группу:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda c: c.data == 'correct_info')
async def correct_info(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    # Сохранение данных в базу
    conn = await connect(**DB_CONFIG)
    mentor_available = await conn.fetchval("""
        SELECT count(*)
        FROM mentors
        WHERE id = $1
        AND registered < max_registered
    """, user_data[user_id]["mentor_id"])

    if mentor_available > 0:
        # Check if subtopic is available
        subtopic_available = await conn.fetchval("""
            SELECT count(*)
            FROM subtopics
            WHERE id = $1
            AND NOT picked
        """, user_data[user_id]["subtopic_id"])
        if subtopic_available > 0:
            await add_user(
                user_data[user_id]["full_name"],
                user_data[user_id]["group_name"],
                user_data[user_id]["topic_id"],
                user_data[user_id]["mentor_id"],
                user_data[user_id]["subtopic_id"],
                user_data[user_id]["additional_info"],
                user_id,
            )
            # Создание кнопок для выбранных действий
            markup = await create_keyboard(
                [
                    "Поддержка",
                    "Статус заявления",
                    "Редактировать заявление",
                    "Удалить заявление",
                    "Назад",
                ]
            )
            # Уведомление пользователя об успешном добавлении
            await bot.send_message(
                callback_query.message.chat.id, "Пользователь успешно добавлен.", reply_markup=markup
            )
            # Установка состояния пользователя как зарегистрированного
            await bot.set_state(user_id, UserStates.registered, callback_query.message.chat.id)
            # Удаление данных пользователя из временного хранилища
            del user_data[user_id]
            await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)

        else:
            await bot.send_message(user_id, "К сожалению, эту тему кто-то уже взял, попробуйте вновь",
                                   reply_markup=InlineKeyboardMarkup(
                                       row_width=2).add(InlineKeyboardButton("Назад", callback_data="edit_info")))
    else:
        await bot.send_message(user_id,
                               "К сожалению, этого ментора уже взяли достаточное количество раз. Попробуйте вновь",
                               reply_markup=InlineKeyboardMarkup(
                                   row_width=2).add(InlineKeyboardButton("Назад", callback_data="back_to_topics")))


@bot.callback_query_handler(func=lambda c: c.data == 'edit_info')
async def edit_info(callback_query: types.CallbackQuery):
    """
    Обрабатывает выбор для редактирования информации пользователя.
    Показывает кнопки для редактирования отдельных полей.
    """
    user_id = callback_query.from_user.id
    # Создаем клавиатуру для выбора редактируемого поля
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton(text="ФИО", callback_data='edit_full_name'))
    keyboard.add(InlineKeyboardButton(text="Группа", callback_data='edit_group_name'))
    keyboard.add(InlineKeyboardButton(text="Изменить тему", callback_data='edit_topic'))
    keyboard.add(InlineKeyboardButton(text="Изменить ментора", callback_data='edit_mentor'))
    keyboard.add(InlineKeyboardButton(text="Изменить подтему", callback_data='edit_subtopic'))
    keyboard.add(InlineKeyboardButton(text="Доп. информация", callback_data='edit_additional_info'))
    keyboard.add(InlineKeyboardButton(text="Назад", callback_data='back_to_check'))

    await bot.send_message(callback_query.message.chat.id, "Что вы хотите изменить?", reply_markup=keyboard)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)


# Обработка нажатия кнопки для редактирования ФИО
@bot.callback_query_handler(func=lambda c: c.data == 'edit_full_name')
async def edit_full_name(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    await bot.set_state(user_id, UserStates.edit_name, callback_query.message.chat.id)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.send_message(callback_query.message.chat.id, "Введите новое ФИО:")


# Обработка нажатия кнопки для редактирования группы
@bot.callback_query_handler(func=lambda c: c.data == 'edit_group_name')
async def edit_group_name(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    await bot.set_state(user_id, UserStates.edit_group, callback_query.message.chat.id)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.send_message(callback_query.message.chat.id, "Введите новую группу:")


# Обработка нажатия кнопки для редактирования дополнительной информации
@bot.callback_query_handler(func=lambda c: c.data == 'edit_additional_info')
async def edit_additional_info(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    await bot.set_state(user_id, UserStates.edit_additional_info, callback_query.message.chat.id)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.send_message(callback_query.message.chat.id,
                           "Введите новую дополнительную информацию (или пропустите, отправив '-'):")


# Вызов общей функции handle_edit для каждого поля

@bot.message_handler(state=UserStates.edit_name)
async def edit_name(message):
    await handle_edit(
        message,
        "full_name",
        r"^[А-Яа-яёЁ\s\-]+$",  # Регулярное выражение для проверки ФИО
        "ФИО изменено",
        "Вы использовали недопустимые символы. Попробуйте вновь:"
    )


@bot.message_handler(state=UserStates.edit_group)
async def edit_group(message):
    await handle_edit(
        message,
        "group_name",
        r"^[А-Яа-яёЁ]{2}\d-\d{2}$",  # Регулярное выражение для проверки группы
        "группа изменена",
        "Вы использовали недопустимые символы. Попробуйте вновь:"
    )


@bot.message_handler(state=UserStates.edit_additional_info)
async def edit_additional_info(message):
    await handle_edit(
        message,
        "additional_info",
        None,
        "дополнительная информация изменена",
        None,
        True
    )


@bot.callback_query_handler(func=lambda c: c.data == 'edit_topic')
async def edit_topic(callback_query: types.CallbackQuery):
    conn = await connect(**DB_CONFIG)
    keyboard = await topics_keyboard(conn)
    keyboard.add(InlineKeyboardButton(text="Назад", callback_data='start'))
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.send_message(callback_query.message.chat.id, "Выберите новую тему:", reply_markup=keyboard)
    await bot.set_state(callback_query.from_user.id, UserStates.edit_topic, callback_query.message.chat.id)
    await conn.close()


@bot.callback_query_handler(func=lambda c: c.data == 'edit_mentor')
async def edit_mentor(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    conn = await connect(**DB_CONFIG)
    keyboard = await mentors_keyboard(conn, user_data[user_id].get('topic_id'))
    back_button = InlineKeyboardButton(text="Назад", callback_data='back_to_topics')
    keyboard.add(back_button)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.send_message(callback_query.message.chat.id, "Выберите нового ментора:", reply_markup=keyboard)
    await bot.set_state(callback_query.from_user.id, UserStates.edit_topic, callback_query.message.chat.id)
    await conn.close()


@bot.callback_query_handler(func=lambda c: c.data == 'edit_subtopic')
async def edit_subtopic(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    conn = await connect(**DB_CONFIG)
    keyboard = await subtopics_keyboard(conn, user_data[user_id].get('mentor_id'))
    back_button = InlineKeyboardButton(text="Назад", callback_data='back_to_mentors')
    keyboard.add(back_button)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.send_message(callback_query.message.chat.id, "Выберите новую подтему:", reply_markup=keyboard)
    await bot.set_state(callback_query.from_user.id, UserStates.edit_topic, callback_query.message.chat.id)
    await conn.close()


@bot.callback_query_handler(func=lambda c: c.data == 'back_to_check')
async def back_to_check(callback_query: types.CallbackQuery):
    try:
        await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    except Exception as e:
        print(e, " Do nothing")
    user_id = callback_query.from_user.id
    conn = await connect(**DB_CONFIG)
    response = (
        f"ФИО: {user_data[user_id]['full_name']}\n"
        f"Группа: {user_data[user_id]['group_name']}\n"
        f"Тема: {await conn.fetchval('SELECT full_name FROM topics WHERE id = $1', user_data[user_id]['topic_id'])}\n"
        f"Ментор: {await conn.fetchval('SELECT full_name FROM mentors WHERE id = $1', user_data[user_id]['mentor_id'])}\n"
        f"Подтема: {await conn.fetchval('SELECT full_name FROM subtopics WHERE id = $1', user_data[user_id]['subtopic_id'])}\n"
        f"Доп. информация: {user_data[user_id]['additional_info']}\n"
    )
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton(text="Да", callback_data='correct_info'))
    keyboard.add(InlineKeyboardButton(text="Нет", callback_data='edit_info'))
    await bot.send_message(
        callback_query.message.chat.id, "Проверь, верно ли всё:\n" + response, reply_markup=keyboard
    )


async def handle_edit(
        message, field_name, regex, success_message, error_message, allow_none=True
):
    """
    Обрабатывает редактирование различных полей пользователя.

    :param message: Объект сообщения от пользователя.
    :param field_name: Название поля, которое редактируется.
    :param regex: Регулярное выражение для валидации текста.
    :param success_message: Сообщение об успешном изменении.
    :param error_message: Сообщение об ошибке при неправильном вводе.
    :param allow_none: Разрешено ли пустое значение.

    :return: None
    """
    user_id = message.from_user.id
    text = message.text

    if text == "Назад":
        await start(message)
        return

    if not allow_none and (text == "-" or not text.strip()):
        await bot.reply_to(
            message, "Это поле не может быть пустым. Пожалуйста, введите значение."
        )
        return

    if regex and not re.match(regex, text):
        if error_message:
            await bot.reply_to(message, error_message)
        return

    if text == "-":
        text = None

    if user_data.get(user_id):
        user_data[user_id][field_name] = text
        await bot.reply_to(message, f"Готово, {success_message}")
        conn = await connect(**DB_CONFIG)
        response = (
            f"ФИО: {user_data[user_id]['full_name']}\n"
            f"Группа: {user_data[user_id]['group_name']}\n"
            f"Тема: {await conn.fetchval('SELECT full_name FROM topics WHERE id = $1', user_data[user_id].get('topic_id'))}\n"
            f"Ментор: {await conn.fetchval('SELECT full_name FROM mentors WHERE id = $1', user_data[user_id].get('mentor_id'))}\n"
            f"Подтема: {await conn.fetchval('SELECT full_name FROM subtopics WHERE id = $1', user_data[user_id]['subtopic_id'])}\n"
            f"Доп. информация: {user_data[user_id]['additional_info']}\n"
        )
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(InlineKeyboardButton(text="Да", callback_data='correct_info'))
        keyboard.add(InlineKeyboardButton(text="Нет", callback_data='edit_info'))
        await bot.send_message(
            message.chat.id, "Проверь, верно ли всё:\n" + response, reply_markup=keyboard
        )
    else:
        await update_database(user_id, field_name, text)
        markup = await create_keyboard(
            [
                "Поддержка",
                "Статус заявления",
                "Редактировать заявление",
                "Удалить заявление",
                "Назад",
            ]
        )
        await set_state_and_reply(
            message, UserStates.registered, f"Готово, {success_message}", markup
        )


async def get_user_handler(message):
    """
    Обрабатывает запрос на получение информации о пользователе.

    Функция ищет пользователя по его идентификатору и формирует ответ с деталями,
    такими как ФИО, группа, тема, подтема, дополнительная информация и ментор.

    :param message: Объект сообщения от пользователя, содержащий информацию о пользователе.

    :return: None
    """
    user_id = message.from_user.id
    data = await get_user_by_id(user_id)
    conn = await connect(**DB_CONFIG)
    if data:
        # Формируем ответ, если пользователь найден
        response = (
            f"ФИО: {data[1]}\n"
            f"Группа: {data[2]}\n"
            f"Тема: {await conn.fetchval('SELECT full_name FROM topics where id = $1', data[3])}\n"
            f"Ментор: {await conn.fetchval('SELECT full_name FROM mentors where id = $1', data[4])}\n"
            f"Подтема: {await conn.fetchval('SELECT full_name FROM subtopics WHERE id = $1', data[5])}\n"
            f"Доп. информация: {data[6]}\n"
        )
    else:
        response = "Пользователь не найден."  # Если пользователь не найден

    await bot.reply_to(message, response)  # Ответ пользователю


# Обработчик команды /start
@bot.message_handler(commands=["start"])
async def start(message: types.Message) -> None:
    """
    Обрабатывает команду /start и отправляет приветственное сообщение
    с вопросом о регистрации.

    :param message: Объект сообщения, содержащий информацию о команде и пользователе.
    :return: None
    """
    if message.from_user.id in mentor_table:
        name = mentor_table[message.from_user.id][0]
        keyboard = await create_keyboard([
            "Записавшиеся студенты",
            "Поддержка"
        ])
        await bot.set_state(message.from_user.id, UserStates.mentor, message.from_user.id)
        await bot.reply_to(message, f"Добрый день, {name}, что Вы желаете сделать?", reply_markup=keyboard)
    data = await get_user_by_id(message.from_user.id)
    if data:
        await set_state_and_reply(
            message, UserStates.registered, f"С возвращением, {data[1]}!"
        )
        markup = await create_keyboard(
            [
                "Поддержка",
                "Статус заявления",
                "Редактировать заявление",
                "Удалить заявление",
                "Назад",
            ]
        )
        await bot.send_message(
            message.chat.id, "Что ты хочешь сделать?", reply_markup=markup
        )
    else:
        try:
            user_data.pop(
                message.from_user.id, None
            )  # .pop() avoids KeyError, None prevents crash
        except Exception as e:
            print(
                f"Error deleting user data: {e}"
            )  # Log the error but don't stop execution
        await bot.set_state(
            message.from_user.id, UserStates.not_registered, message.chat.id
        )
        markup = await create_keyboard(
            [
                "Поддержка",
                "Регистрация",
                "Узнать темы",
                "Назад",
            ]
        )
        await bot.send_message(
            message.chat.id,
            f"Привет, {message.from_user.first_name}! Что ты хочешь сделать?",
            reply_markup=markup,
        )


@bot.message_handler(content_types=["text"], state=UserStates.mentor)
async def info(message):
    if message.text == "Поддержка":
        await bot.reply_to(
            message,
            "По всем вопросам обращайтесь к главе менторства: [@Jezzixxx_Jinx](https://t.me/Jezzixxx_Jinx)",
            parse_mode="Markdown",
        )
    if message.text == "Записавшиеся студенты":
        conn = await connect(**DB_CONFIG)
        data = await conn.fetchval("""SELECT user_id FROM users WHERE mentor_id == $1""",
                                   mentor_table[message.from_user.id][1])
        for person in data:
            info = await get_user_by_id(person)
            response = (
                f"ФИО: {info[1]}\n"
                f"Группа: {info[2]}\n"
                f"Тема: {await conn.fetchval('SELECT full_name FROM topics where id = $1', info[3])}\n"
                f"Ментор: {await conn.fetchval('SELECT full_name FROM mentors where id = $1', info[4])}\n"
                f"Подтема: {await conn.fetchval('SELECT full_name FROM subtopics WHERE id = $1', info[5])}\n"
                f"Доп. информация: {info[6]}\n"
                f"Тэг: [@{info[1]}](tg://user?id={info[7]})"
            )
            await bot.send_message(message.from_user.id, response)


# Обработчик текстовых сообщений
@bot.message_handler(content_types=["text"], state=UserStates.registered)
async def info(message: types.Message) -> None:
    """
    Обрабатывает текстовые сообщения и реагирует на выбор пользователя.

    :param message: Объект сообщения, содержащий текст и информацию о пользователе.
    :return: None
    """
    options = {
        "Поддержка": {
            "function": support,
        },
        "Назад": {
            "function": start,
        },
        "Статус заявления": {
            "function": status,
        },
        "Редактировать заявление": {
            "function": edit,
        },
        "Удалить заявление": {
            "function": delete_handler,
        },
    }

    user_input = message.text
    if user_input in options:
        option = options[user_input]
        await option["function"](message)

    else:
        # Если текст не соответствует известным командам
        await bot.reply_to(
            message,
            text=(
                "Я не понимаю, что вы имеете в виду. "
                "Пожалуйста, выберите один из предложенных вариантов."
            ),
        )


@bot.message_handler(content_types=["text"], state=UserStates.not_registered)
async def info(message: types.Message) -> None:
    """
    Обрабатывает текстовые сообщения и реагирует на выбор пользователя.

    :param message: Объект сообщения, содержащий текст и информацию о пользователе.
    :return: None
    """
    options = {
        "Поддержка": {
            "function": support,
        },
        "Назад": {
            "function": start,
        },
        "Регистрация": {
            "function": registration,
        },
        "Узнать темы": {
            "function": topics,
        },
    }

    user_input = message.text
    if user_input in options:
        option = options[user_input]
        await option["function"](message)

    else:
        # Если текст не соответствует известным командам
        await bot.reply_to(
            message,
            text=(
                "Я не понимаю, что вы имеете в виду. "
                "Пожалуйста, выберите один из предложенных вариантов."
            ),
        )


async def add_user(
        full_name, group_name, topic, subtopic, additional_info, mentor, user_id
):
    """
    Добавляет нового пользователя в базу данных.

    :param full_name: Полное имя пользователя
    :param group_name: название группы пользователя
    :param topic: тема пользователя
    :param subtopic: подтема пользователя
    :param additional_info: дополнительная информация о пользователе
    :param mentor: имя ментора пользователя
    :param user_id: уникальный идентификатор пользователя
    """

    conn = await connect(**DB_CONFIG)  # Подключаемся к базе данных

    # Вставляем данные в таблицу users
    await conn.execute(
        """INSERT INTO users (full_name, group_name, topic_id, mentor_id, subtopic_id, 
                              additional_info, user_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7)""",
        full_name,
        group_name,
        topic,
        subtopic,
        additional_info,
        mentor,
        user_id,
    )
    await conn.execute("""
                UPDATE mentors
                SET registered = registered + 1
                WHERE id = $1
            """, mentor)
    await conn.execute("""
    UPDATE subtopics
    SET picked = TRUE
    WHERE id = $1""", subtopic)
    await conn.close()  # Закрываем соединение


async def get_user_by_id(user_id):
    """
    Получает данные пользователя из базы данных по его ID.

    :param user_id: Уникальный идентификатор пользователя
    :return: данные пользователя или None, если пользователь не найден
    """

    conn = await connect(**DB_CONFIG)  # Подключаемся к базе данных
    data = await conn.fetchrow(
        """SELECT * FROM users WHERE user_id = $1""", user_id
    )  # Получаем данные пользователя
    await conn.close()  # Закрываем соединение
    return data  # Возвращаем данные пользователя


# Асинхронная функция для статуса заявления
async def status(message: types.Message) -> None:
    """
    Отправляет сообщение о том, что статус заявления в разработке.

    :param message: Объект сообщения, содержащий информацию о пользователе.
    :return: None
    """
    await get_user_handler(message)


# Асинхронная функция для редактирования заявления
async def edit(message: types.Message) -> None:
    await bot.send_message(message.chat.id, "Приступим к изменению данных", reply_markup=types.ReplyKeyboardRemove())
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("ФИО", callback_data="edit_fio_2")],
        [InlineKeyboardButton("Группа", callback_data="edit_group_2")],
        [InlineKeyboardButton("Тема", callback_data="edit_topic_2")],
        [InlineKeyboardButton("Ментор", callback_data="edit_mentor_2")],
        [InlineKeyboardButton("Подтема", callback_data="edit_subtopic_2")],
        [InlineKeyboardButton("Доп. информация", callback_data="edit_additional_2")],
        [InlineKeyboardButton("Назад", callback_data="edit_back_2")],
    ], row_width=2)

    await bot.send_message(
        chat_id=message.chat.id,
        text="Выбери, что хочешь изменить: ",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda c: c.data == "edit_fio_2")
async def handle_fio_edit(callback_query):
    user_id = callback_query.from_user.id
    await bot.set_state(user_id, UserStates.edit_name_2, callback_query.message.chat.id)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Назад", callback_data="to_edit")]
    ], row_width=2)
    await bot.send_message(callback_query.message.chat.id, "Введите новое ФИО:", reply_markup=markup)


@bot.message_handler(state=UserStates.edit_name_2)
async def edit_name_2(message: types.Message):
    russian_letter_regex = r"^[А-Яа-яёЁ\s\-]+$"
    if bool(re.match(russian_letter_regex, message.text)):
        await update_database(message.from_user.id, "full_name", message.text)
        await bot.reply_to(message, "Данные успешно изменены")
        await bot.set_state(message.from_user.id, UserStates.registered, message.chat.id)
        markup = await create_keyboard(
            [
                "Поддержка",
                "Статус заявления",
                "Редактировать заявление",
                "Удалить заявление",
                "Назад",
            ]
        )
        await bot.send_message(
            message.chat.id, "Что ты хочешь сделать?", reply_markup=markup
        )
    else:
        markup = InlineKeyboardMarkup([
            InlineKeyboardButton("Назад", callback_data="to_edit")
        ])
        await bot.reply_to(
            message, "Вы использовали недопустимые символы. Попробуйте вновь:", reply_markup=markup
        )


@bot.callback_query_handler(func=lambda c: c.data == "edit_group_2")
async def handle_group_edit(callback_query):
    user_id = callback_query.from_user.id
    await bot.set_state(user_id, UserStates.edit_group_2, callback_query.message.chat.id)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("Назад", callback_data="to_edit")]
    ], row_width=2)
    await bot.send_message(callback_query.message.chat.id, "Введите новую группу:", reply_markup=markup)


@bot.message_handler(state=UserStates.edit_group_2)
async def edit_group_2(message):
    format_regex = r"^[А-Яа-яёЁ]{2}\d-\d{2}$"
    if bool(re.match(format_regex, message.text)):
        await update_database(message.from_user.id, "group_name", message.text)
        await bot.reply_to(message, "Данные успешно изменены")
        await bot.set_state(message.from_user.id, UserStates.registered, message.chat.id)
        markup = await create_keyboard(
            [
                "Поддержка",
                "Статус заявления",
                "Редактировать заявление",
                "Удалить заявление",
                "Назад",
            ]
        )
        await bot.send_message(
            message.chat.id, "Что ты хочешь сделать?", reply_markup=markup
        )
    else:
        markup = InlineKeyboardMarkup([
            InlineKeyboardButton("Назад", callback_data="to_edit")
        ])
        await bot.reply_to(
            message, "Вы использовали недопустимые символы. Попробуйте вновь:", reply_markup=markup
        )


# Создаем клавиатуру для тем с кнопкой "Назад"
async def edit_topics_keyboard(conn):
    topics = await get_topics(conn)
    keyboard = InlineKeyboardMarkup(row_width=2)

    for topic in topics:
        topic_button = InlineKeyboardButton(
            text=topic['full_name'],
            callback_data=f'editing_topic,{topic["id"]}'
        )
        keyboard.add(topic_button)
    return keyboard


# Создаем клавиатуру для менторов с кнопкой "Назад"
async def edit_mentors_keyboard(conn, topic_id):
    mentor_ids = await conn.fetch("SELECT mentor FROM topics WHERE id = $1", topic_id)
    mentors = await get_mentors_by_topic(conn, mentor_ids)
    keyboard = InlineKeyboardMarkup(row_width=2)

    for mentor in mentors:
        mentor_button = InlineKeyboardButton(
            text=mentor['full_name'],
            callback_data=f'editing_mentor,{mentor["id"]}'
        )
        keyboard.add(mentor_button)

    # Добавляем кнопку "Назад"

    return keyboard


# Создаем клавиатуру для подтем с кнопкой "Назад"
async def edit_subtopics_keyboard(conn, mentor_id):
    subtopic_id = await conn.fetch("SELECT subtopic FROM mentors WHERE id = $1", mentor_id)
    subtopics = await get_subtopics_by_mentor(conn, subtopic_id)
    keyboard = InlineKeyboardMarkup(row_width=2)

    for subtopic in subtopics:
        subtopic_button = InlineKeyboardButton(
            text=subtopic['full_name'],
            callback_data=f'editing_subtopic,{subtopic["id"]}'
        )
        keyboard.add(subtopic_button)

    # Добавляем кнопку "Назад"

    return keyboard


@bot.callback_query_handler(func=lambda c: c.data == "edit_topic_2")
async def handle_topic_edit(callback_query):
    user_data[callback_query.from_user.id] = {}
    conn = await connect(**DB_CONFIG)
    keyboard = await edit_topics_keyboard(conn)
    keyboard.add(InlineKeyboardButton(text="Назад", callback_data='to_edit'))
    await bot.send_message(callback_query.message.chat.id, "Выберите тему:", reply_markup=keyboard)
    await conn.close()


@bot.callback_query_handler(func=lambda c: c.data == "edit_mentor_2")
async def handle_mentor_edit(callback_query):
    user_data[callback_query.from_user.id] = {}
    conn = await connect(**DB_CONFIG)
    data = await get_user_by_id(callback_query.from_user.id)
    keyboard = await edit_mentors_keyboard(conn, data[3])
    await bot.send_message(callback_query.message.chat.id, "Выберите ментора:", reply_markup=keyboard)
    await conn.close()


@bot.callback_query_handler(func=lambda c: c.data == "edit_subtopic_2")
async def handle_subtopic_edit(callback_query):
    user_data[callback_query.from_user.id] = {}
    conn = await connect(**DB_CONFIG)
    data = await get_user_by_id(callback_query.from_user.id)
    keyboard = await edit_subtopics_keyboard(conn, data[4])
    await bot.send_message(callback_query.message.chat.id, "Выберите подтему:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda c: c.data.startswith("editing_topic"))
async def process_editing_topic(callback_query):
    user_id = callback_query.from_user.id
    topic_id = int(callback_query.data.split(',')[1])
    user_data[user_id]['topic_id'] = topic_id
    conn = await connect(**DB_CONFIG)
    keyboard = await edit_mentors_keyboard(conn, topic_id)
    back_button = InlineKeyboardButton(text="Назад", callback_data='to_editing_topics')
    keyboard.add(back_button)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.send_message(callback_query.message.chat.id, "Выберите ментора:", reply_markup=keyboard)
    await conn.close()


@bot.callback_query_handler(func=lambda c: c.data.startswith("editing_mentor"))
async def process_editing_mentor(callback_query):
    user_id = callback_query.from_user.id
    mentor_id = int(callback_query.data.split(',')[1])
    user_data[user_id]['mentor_id'] = mentor_id
    conn = await connect(**DB_CONFIG)
    keyboard = await edit_subtopics_keyboard(conn, mentor_id)
    keyboard.add(InlineKeyboardButton(text="Назад", callback_data='to_editing_mentors'))
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.send_message(callback_query.message.chat.id, "Выберите подтему:", reply_markup=keyboard)
    await conn.close()


@bot.callback_query_handler(func=lambda c: c.data.startswith("editing_subtopic"))
async def process_editing_subtopic(callback_query):
    user_id = callback_query.from_user.id
    subtopic_id = int(callback_query.data.split(',')[1])
    user_data[user_id]['subtopic_id'] = subtopic_id
    conn = await connect(**DB_CONFIG)
    mentor_available = await conn.fetchval("""
        SELECT count(*)
        FROM mentors
        WHERE id = $1
        AND registered < max_registered
    """, user_data[user_id]["mentor_id"])

    if mentor_available > 0:
        # Check if subtopic is available
        subtopic_available = await conn.fetchval("""
            SELECT count(*)
            FROM subtopics
            WHERE id = $1
            AND NOT picked
        """, user_data[user_id]["subtopic_id"])
        if subtopic_available > 0:
            if user_data[user_id]['topic_id']:
                await update_database(user_id, 'topic_id', user_data[user_id]['topic_id'])
            if user_data[user_id]['mentor_id']:
                await update_database(user_id, 'mentor_id', user_data[user_id]['mentor_id'])
            if user_data[user_id]['subtopic_id']:
                await update_database(user_id, 'subtopic_id', user_data[user_id]['subtopic_id'])
            await bot.send_message(callback_query.message.chat.id, "Данные успешно изменены")
            await bot.set_state(user_id, UserStates.registered, callback_query.message.chat.id)
            markup = await create_keyboard(
                [
                    "Поддержка",
                    "Статус заявления",
                    "Редактировать заявление",
                    "Удалить заявление",
                    "Назад",
                ]
            )
            await bot.send_message(
                callback_query.message.chat.id, "Что ты хочешь сделать?", reply_markup=markup
            )
        else:
            await bot.send_message(user_id, "К сожалению, эту подтему кто-то уже взял, попробуйте другую",
                                   reply_markup=InlineKeyboardMarkup(
                                       InlineKeyboardButton("Назад", callback_data="to_editing_topics")))
    else:
        await bot.send_message(user_id,
                               "К с ожалению, этого ментора уже взяли достаточное количество раз. Попробуйте вновь",
                               reply_markup=InlineKeyboardMarkup(
                                   (InlineKeyboardButton("Назад", callback_data="to_editing_topics"))))


@bot.callback_query_handler(func=lambda c: c.data == "to_editing_topics")
async def to_editing_topics(callback_query):
    conn = await connect(**DB_CONFIG)
    keyboard = await edit_topics_keyboard(conn)
    keyboard.add(InlineKeyboardButton(text="Назад", callback_data='to_edit'))
    await bot.send_message(callback_query.message.chat.id, "Выберите тему:", reply_markup=keyboard)
    await conn.close()


@bot.callback_query_handler(func=lambda c: c.data == "to_editing_mentors")
async def to_editing_mentors(callback_query):
    conn = await connect(**DB_CONFIG)
    keyboard = await edit_mentors_keyboard(conn, user_data[callback_query.from_user.id]['topic_id'])
    keyboard.add(InlineKeyboardButton(text="Назад", callback_data='to_editing_topics'))
    await bot.send_message(callback_query.message.chat.id, "Выберите ментора:", reply_markup=keyboard)
    await conn.close()


@bot.callback_query_handler(func=lambda c: c.data == "edit_additional_2")
async def handle_additional_edit(callback_query):
    user_id = callback_query.from_user.id
    await bot.set_state(user_id, UserStates.edit_additional_info_2, callback_query.message.chat.id)
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    markup = InlineKeyboardMarkup([
        InlineKeyboardButton("Назад", callback_data="to_edit")
    ])
    await bot.send_message(callback_query.message.chat.id,
                           "Введите новую дополнительную информацию (или пропустите, отправив '-'):",
                           reply_markup=markup)


@bot.message_handler(state=UserStates.edit_additional_info_2)
async def edit_additional_2(message: types.Message):
    user_id = message.from_user.id
    if message.text == "-": message.text = None
    await update_database(user_id, "additional_info", message.text)
    await bot.reply_to(message, "Данные успешно изменены")
    await bot.set_state(message.from_user.id, UserStates.registered, message.chat.id)
    markup = await create_keyboard(
        [
            "Поддержка",
            "Статус заявления",
            "Редактировать заявление",
            "Удалить заявление",
            "Назад",
        ]
    )
    await bot.send_message(
        message.chat.id, "Что ты хочешь сделать?", reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data == "edit_back_2")
async def handle_back(callback_query):
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.id)
    await bot.set_state(callback_query.message.chat.id, UserStates.registered)
    markup = await create_keyboard(
        [
            "Поддержка",
            "Статус заявления",
            "Редактировать заявление",
            "Удалить заявление",
            "Назад",
        ]
    )
    await bot.send_message(
        callback_query.message.chat.id, "Что ты хочешь сделать?", reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data == "to_edit")
async def to_edit(callback_query):
    try:
        user_data.pop(callback_query.from_user.id, None)
    except KeyError as e:
        print(e, " That's fine")
    await bot.send_message(callback_query.message.chat.id, "Вернемся к изменению данных",
                           reply_markup=types.ReplyKeyboardRemove())
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("ФИО", callback_data="edit_fio")],
        [InlineKeyboardButton("Группа", callback_data="edit_group")],
        [InlineKeyboardButton("Тема", callback_data="edit_topic")],
        [InlineKeyboardButton("Ментор", callback_data="edit_mentor")],
        [InlineKeyboardButton("Подтема", callback_data="edit_subtopic")],
        [InlineKeyboardButton("Доп. информация", callback_data="edit_additional")],
        [InlineKeyboardButton("Назад", callback_data="edit_back")],
    ], row_width=2)

    await bot.send_message(
        chat_id=callback_query.message.chat.id,
        text="Выбери, что хочешь изменить: ",
        reply_markup=markup,
    )


# Асинхронная функция для удаления заявления
async def delete_handler(message: types.Message) -> None:
    """
    Запрашивает у пользователя подтверждение на удаление заявления.

    :param message: Объект сообщения, содержащий информацию о пользователе.
    :return: None
    """
    # Создание клавиатуры с кнопками "Да" и "Нет"
    markup = await create_keyboard(
        [
            "Да",
            "Нет",
        ]
    )

    # Запрос подтверждения на удаление
    await bot.send_message(
        message.chat.id,
        text="Точно удалить?",
        reply_markup=markup,
    )
    await bot.set_state(message.chat.id, UserStates.deleting, message.chat.id)


@bot.message_handler(state=UserStates.deleting)
async def delete(message):
    """
    Обрабатывает удаление данных пользователя в зависимости от текста сообщения.

    Если пользователь отвечает "Нет", данные не удаляются, и отправляется сообщение об этом с предложением
    других действий. В противном случае пользователь удаляется из базы данных.

    :param message: Объект сообщения от пользователя, содержащий текст и идентификатор пользователя.

    :return: None
    :raises Exception: Исключение может быть вызвано при ошибках подключения к базе данных или выполнении SQL-запроса.
    """
    if message.text == "Нет":
        markup = await create_keyboard(
            [
                "Поддержка",
                "Статус заявления",
                "Редактировать заявление",
                "Удалить заявление",
                "Назад",
            ]
        )
        await set_state_and_reply(
            message, UserStates.registered, "Данные не удалены.", markup
        )
    else:
        conn = await connect(**DB_CONFIG)
        await conn.execute(
            """DELETE FROM users WHERE user_id = $1""", message.from_user.id
        )
        await conn.close()
        markup = await create_keyboard(
            [
                "Поддержка",
                "Регистрация",
                "Узнать темы",
                "Назад",
            ]
        )
        await set_state_and_reply(
            message, UserStates.not_registered, "Данные успешно удалены.", markup
        )


# Асинхронная функция для регистрации
async def registration(message: types.Message) -> None:
    """
    Сообщает пользователю, что функция регистрации в разработке.

    :param message: Объект сообщения, содержащий информацию о пользователе.
    :return: None
    """
    await start_add_user(message)


# Асинхронная функция для узнавания тем
async def topics(message: types.Message) -> None:
    """
    Отправляет сообщение о том, что будет представлен список тем.

    :param message: Объект сообщения, содержащий информацию о пользователе.
    :return: None
    """
    user_data[message.from_user.id] = {}
    conn = await connect(**DB_CONFIG)
    await bot.delete_message(message.chat.id, (
        await bot.send_message(message.chat.id, "-", reply_markup=types.ReplyKeyboardRemove())).id)
    keyboard = await topics_keyboard(conn, 42)
    keyboard.add(InlineKeyboardButton(text="Назад", callback_data='start'))
    await bot.send_message(message.chat.id, "Темы, которые у нас представлены:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda c: c.data.startswith("infotopic_"))
async def info_topic(callback_query: types.CallbackQuery) -> None:
    conn = await connect(**DB_CONFIG)
    await bot.delete_message(callback_query.from_user.id, callback_query.message.id)
    topic_id = int(callback_query.data.split('_')[1])
    user_data[callback_query.from_user.id]["topic_id"] = topic_id
    full_name = await conn.fetchval("SELECT full_name FROM topics WHERE id = $1", topic_id)
    description = await conn.fetchval("SELECT description FROM topics WHERE id = $1", topic_id)
    keyboard = await mentors_keyboard(conn, topic_id, 42)
    back_button = InlineKeyboardButton(text="Назад", callback_data='back_to_info_topic')
    keyboard.add(back_button)
    await bot.send_message(callback_query.message.chat.id,
                           f"{full_name}:\n{description}\n\nМенторы, представленные на данном направлении:",
                           reply_markup=keyboard)


@bot.callback_query_handler(func=lambda c: c.data == 'back_to_info_topic')
async def back_to_info_topic(callback_query: types.CallbackQuery) -> None:
    await bot.delete_message(callback_query.from_user.id, callback_query.message.id)
    await topics(callback_query.message)


@bot.callback_query_handler(func=lambda c: c.data.startswith("infomentor_"))
async def info_mentor(callback_query: types.CallbackQuery) -> None:
    conn = await connect(**DB_CONFIG)
    await bot.delete_message(callback_query.from_user.id, callback_query.message.id)
    mentor_id = int(callback_query.data.split('_')[1])
    user_data[callback_query.from_user.id]["mentor_id"] = mentor_id
    description = int(await conn.fetchval("SELECT description FROM mentors WHERE id = $1", mentor_id))
    keyboard = await subtopics_keyboard(conn, mentor_id, 42)
    # Добавляем кнопку "Назад"
    back_button = InlineKeyboardButton(text="Назад",
                                       callback_data=f'infotopic_{user_data[callback_query.from_user.id]["topic_id"]}')
    keyboard.add(back_button)
    await bot.forward_message(callback_query.message.chat.id, -1002325501843, description - 1)
    await bot.forward_message(callback_query.message.chat.id, -1002325501843, description)
    await bot.send_message(callback_query.message.chat.id, "Подтемы, которые ведутся этим ментором:",
                           reply_markup=keyboard)


@bot.callback_query_handler(func=lambda c: c.data.startswith('infosubtopic_'))
async def info_subtopic(callback_query: types.CallbackQuery) -> None:
    await bot.set_state(callback_query.from_user.id, UserStates.not_registered, callback_query.message.chat.id)
    await bot.delete_message(callback_query.from_user.id, callback_query.message.id)
    await bot.delete_message(callback_query.from_user.id, callback_query.message.id - 1)
    await bot.delete_message(callback_query.from_user.id, callback_query.message.id - 2)
    conn = await connect(**DB_CONFIG)
    subtopic_id = int(callback_query.data.split('_')[1])
    user_data[callback_query.from_user.id]["subtopic_id"] = subtopic_id
    full_name = await conn.fetchval("SELECT full_name FROM subtopics WHERE id = $1", subtopic_id)
    description = await conn.fetchval("SELECT description FROM subtopics WHERE id = $1", subtopic_id)
    keyboard = InlineKeyboardMarkup(row_width=2)
    back_button = InlineKeyboardButton(text="Назад",
                                       callback_data=f'infomentor_{user_data[callback_query.from_user.id]["mentor_id"]}')
    keyboard.add(back_button)
    keyboard.add(InlineKeyboardButton(text="Зарегистрироваться", callback_data="step_reg"))
    await bot.send_message(callback_query.message.chat.id, f'{full_name}:\n{description}', reply_markup=keyboard)


@bot.callback_query_handler(func=lambda c: c.data.startswith('step_reg'))
async def step_reg(callback_query: types.CallbackQuery) -> None:
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton(text="Назад",
                                      callback_data=f'infosubtopic_{user_data[callback_query.from_user.id]["subtopic_id"]}'))
    await bot.delete_message(callback_query.from_user.id, callback_query.message.id)
    if user_data[callback_query.from_user.id]['mentor_id'] == 3:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text="Назад",
                                          callback_data=f'infosubtopic_{user_data[callback_query.from_user.id]["subtopic_id"]}'))
        await bot.send_message(callback_query.message.chat.id,
                               "Алексей Журин принимает студентов по предварительной проверке. Свяжитесь с ним для подробной информации:")
        await bot.forward_message(callback_query.message.chat.id, -1002325501843, 18)
        await bot.send_message(callback_query.message.chat.id, "Введите пароль:\n", reply_markup=keyboard)
        await bot.set_state(callback_query.from_user.id, UserStates.Zhurin, callback_query.from_user.id)
    else:
        await bot.set_state(callback_query.from_user.id, UserStates.full_name, callback_query.message.chat.id)
        await bot.send_message(callback_query.message.chat.id, f"Введите ваше ФИО:", reply_markup=keyboard)


async def support(message: types.Message) -> None:
    """
    Отправляет сообщение с контактами поддержки.

    :param message: Объект сообщения, содержащий информацию о пользователе.
    :return: None
    """
    await bot.reply_to(
        message,
        "По всем вопросам обращайтесь к главе менторства: [@Jezzixxx_Jinx](https://t.me/Jezzixxx_Jinx)",
        parse_mode="Markdown",
    )


async def edit_full_name_handler(message) -> None:
    """
    Обрабатывает запрос на изменение ФИО пользователя.
    """
    markup = await create_keyboard(["Назад"])
    await set_state_and_reply(
        message, UserStates.edit_name, "Введите новое ФИО:", markup
    )


async def edit_group_name_handler(message) -> None:
    """
    Обрабатывает запрос на изменение группы пользователя.
    """
    markup = await create_keyboard(["Назад"])
    await set_state_and_reply(
        message, UserStates.edit_group, "Введите новое название группы:", markup
    )


async def edit_topic_handler(message) -> None:
    """
    Обрабатывает запрос на изменение темы пользователя.
    """
    markup = await create_keyboard(["Назад"])
    await set_state_and_reply(
        message, UserStates.edit_topic, "Введите новую тему:", markup
    )


async def edit_subtopic_handler(message) -> None:
    """
    Обрабатывает запрос на изменение подтемы пользователя.
    """
    markup = await create_keyboard(["Назад"])
    await set_state_and_reply(
        message, UserStates.edit_subtopic, "Введите новую подтему:", markup
    )


async def edit_additional_info_handler(message) -> None:
    """
    Обрабатывает запрос на изменение дополнительной информации пользователя.
    """
    markup = await create_keyboard(["Назад"])
    await set_state_and_reply(
        message,
        UserStates.edit_additional_info,
        "Введите дополнительную информацию:",
        markup,
    )


async def edit_mentor_handler(message) -> None:
    """
    Обрабатывает запрос на изменение ментора пользователя.
    """
    markup = await create_keyboard(["Назад"])
    await set_state_and_reply(
        message, UserStates.edit_mentor, "Введите имя нового ментора:", markup
    )


# Инструмент для упрощения создания клавиатуры с кнопками в Telegram
async def create_keyboard(buttons: List[str]) -> types.ReplyKeyboardMarkup:
    """
    Создает клавиатуру с заданными кнопками.

    :param buttons: Список текстов кнопок.
    :return: Объект ReplyKeyboardMarkup.
    """

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_objs = [types.KeyboardButton(btn) for btn in buttons]

    markup.add(*btn_objs)
    return markup


async def set_state_and_reply(message, new_state, reply_text, markup=None):
    """
    Устанавливает новое состояние пользователя и отправляет ответное сообщение.

    :param message: Объект сообщения, содержащий информацию о пользователе.
    :param new_state: Новое состояние, которое нужно установить.
    :param reply_text: Текст сообщения, которое будет отправлено пользователю.
    :param markup: Параметры для клавиатуры, которая будет отправлена пользователю.
    """

    await bot.set_state(message.from_user.id, new_state, message.chat.id)
    await bot.reply_to(message, reply_text, reply_markup=markup)


# Функция для первичной инициализации базы данных
async def create_database():
    """
    Инициализирует базу данных, создавая таблицу пользователей, если она не существует.

    В таблице хранятся следующие поля:
    - id: уникальный идентификатор пользователя (первичный ключ).
    - full_name: полное имя пользователя (строка, обязателен).
    - group_name: название группы пользователя (строка, обязателен).
    - topic: тема, выбранная пользователем (строка, обязателен).
    - subtopic: подтема, выбранная пользователем (строка, может быть NULL).
    - additional_info: дополнительная информация о пользователе (строка, может быть NULL).
    - mentor: имя ментора пользователя (строка, может быть NULL).
    - user_id: уникальный идентификатор пользователя в Telegram (большое целое, обязателен и уникален).

    :return: None
    """
    conn = await connect(**DB_CONFIG)

    await conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id serial PRIMARY KEY,
            full_name TEXT NOT NULL,
            group_name TEXT NOT NULL,
            topic_id serial NOT NULL,
            mentor_id serial NOT NULL,
            subtopic_id serial NOT NULL,
            additional_info TEXT,
            user_id bigserial NOT NULL UNIQUE)"""
    )

    await conn.execute(
        """CREATE TABLE IF NOT EXISTS topics (
        id serial PRIMARY KEY,
        full_name TEXT NOT NULL,
        description TEXT NOT NULL,
        mentor INTEGER[] NOT NULL
        )"""
    )

    await conn.execute(
        """CREATE TABLE IF NOT EXISTS mentors (
        id serial PRIMARY KEY,
        full_name TEXT NOT NULL,
        description TEXT NOT NULL,
        subtopic INTEGER[] NOT NULL,
        registered INTEGER NOT NULL,
        max_registered INTEGER NOT NULL
        )"""
    )

    await conn.execute(
        """CREATE TABLE IF NOT EXISTS subtopics (
        id serial PRIMARY KEY,
        full_name TEXT NOT NULL,
        description TEXT NOT NULL,
        picked BOOLEAN NOT NULL
        )"""
    )

    await conn.close()


async def update_database(user_id: int, field_name: str, new_value):
    """
    Обновляет значение указанного поля для пользователя в базе данных.

    :param user_id: Уникальный идентификатор пользователя, чьи данные необходимо обновить.
    :param field_name: Название поля, которое нужно обновить.
    :param new_value: Новое значение для указанного поля.

    :return: None
    :raises Exception: Исключение может быть вызвано при ошибках подключения к базе данных или выполнении SQL-запроса.
    """
    conn = await connect(**DB_CONFIG)
    await conn.execute(
        f"UPDATE users SET {field_name} = $1 WHERE user_id = $2", new_value, user_id
    )
    await conn.close()


# Основная функция для запуска бота
async def main() -> None:
    """
    Запускает опрос для получения сообщений от пользователей.

    :return: None
    """
    await create_database()
    await bot.polling()  # Запускаем опрос для получения сообщений


if __name__ == "__main__":
    asyncio.run(main())  # Запускаем всю асинхронную программу
