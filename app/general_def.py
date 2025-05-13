import os
import sqlite3
import random

import aiogram.utils.keyboard
import requests
from requests.exceptions import RequestException

from aiogram import F,Bot, Router # F добавляет обработчик на сообщения от пользователя (он будет принимать всё (картинки, стикеры, контакты))
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InputMediaPhoto

from config import TOKEN

bot = Bot(token = TOKEN)

def get_conversion_rate():
    try:
        url = 'https://api.binance.com/api/v3/ticker/price?symbol=USDTRUB'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return float(response.json()['price'])
    except RequestException:
        return None


def convert_rubles_to_dollars(rubles: float)-> float or None:
    rate = get_conversion_rate()
    if rate is not None:
        try:
            dollars = rubles / rate
            return dollars
        except ZeroDivisionError:
            return 0
    return None


def generate_captcha(user_id: int, id_owner: int):
    a = random.randint(1, 10)
    b = random.randint(1, 10)
    op = random.choice(['+', '-','*'])
    question = f"{a} {op} {b} = ?"
    answer = eval(str(a) + op + str(b)) # Используем eval для вычисления ответа
    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT * FROM captcha WHERE id = ?", (user_id,))
    result_from_db = cursor.fetchone() # берём первую найденную строку
    if result_from_db:
        cursor.execute(f"UPDATE captcha SET answer = ? WHERE id = ?", (int(answer), user_id))
    else:
        cursor.execute(f"INSERT INTO captcha (id,answer,id_owner) VALUES (?, ?, ?)", (user_id, int(answer), id_owner))
    connection.commit()  # сохранение
    connection.close()
    return question

def get_info_user(user_id: int) -> str:
    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()

    cursor.execute(f"SELECT id FROM users WHERE owner_id = ?", (user_id,))
    all_referral_db = cursor.fetchall()  # возьмёт все имеющиеся строки

    cursor.execute(f"SELECT id FROM users WHERE owner_id = ? AND level > 0", (user_id,))
    all_active_referral_db = cursor.fetchall()

    cursor.execute(
        f"SELECT level, balance, selected_currency, total_earned, referral_url, referral_code, user_name, withdrawal_balance"
        f" FROM users WHERE id = ?",
        (user_id,))
    info = cursor.fetchone()  # получим первую найденную

    cursor.execute(f"SELECT percent_one_level FROM levels WHERE level = ?", (info[0],))
    percent = cursor.fetchone()
    connection.close()

    if info[6]: # если есть имя
        name = f'@{info[6]}'
    else:
        name = ' '

    all_referral = 0  # приглашённых рефералов
    all_active_referral = 0  # приглашённых активных рефералов

    withdrawal_balance = (info[7] * 3) / 100  # сумма которую необходимо вычесть для подсчёта процента
    withdrawal_balance = info[7] - withdrawal_balance  # сумма на вывод с учётом комиссии (в рублях)
    sum_input_in_dollars = convert_rubles_to_dollars(withdrawal_balance)  # сумма вывода в долларах
    sum_in_dollars = convert_rubles_to_dollars(info[1])  # сумма баланса в долларах

    sum_input_in_dollars = round(sum_input_in_dollars, 2)  # сокращаем знаки после запятой
    sum_in_dollars = round(sum_in_dollars, 2)

    for _ in all_referral_db:
        all_referral += 1

    for _ in all_active_referral_db:
        all_active_referral += 1

    if sum_in_dollars:
        if info[2] == 'RUB':
            balance_string = f'{float(info[1])}₽ ({sum_in_dollars}$)'
            withdrawal_balance_string = f'{withdrawal_balance}₽ ({sum_input_in_dollars}$)'
        else:
            balance_string = f'{sum_in_dollars}$ ({float(info[1])}₽)'
            withdrawal_balance_string =  f'{sum_input_in_dollars}$ ({withdrawal_balance}₽)'
    else:
        balance_string = f'{float(info[1])}₽'
        withdrawal_balance_string = f'{withdrawal_balance}₽'

    message_text = (f'🪪 Личный кабинет\n\n'
                    f'├ Никнейм: @{name}\n'
                    f'├ ID: {user_id}\n'
                    f'├ Приглашено рефералов: {all_referral}\n'
                    f'├ Приглашено активных рефералов: {all_active_referral}\n'
                    f'╰ Заработано с нами: {info[3]}\n'
                    f'\n'
                    f'• Личные данные для рефералов\n'
                    f'├ Личная код приглашения: <code>{info[5]}</code>\n'
                    f'╰ Личная реф. ссылка: <a href="https://t.me/parser_premium_bot?start=1028495731">зажмите для копирования</a>\n'
                    f'\n'
                    f'• Личный уровень\n'
                    f'├ Уровень: {info[0]}\n'
                    f'╰ Процент реферального возврата: {percent[0]}\n'
                    f'\n'
                    f'💸 Финансы\n'
                    f'├ Баланс: {balance_string}\n'
                    f'╰ На выводе: {withdrawal_balance_string}')

    return message_text

def show_message_for_all_mailing(user_id: int)-> list:
    # str первый возвращаемый параметр это сообщение
    # str второй параметр путь к фото (если он есть, то необходимо отослать фото)

    message_for_user = 'Текущие сообщение:\n'
    directory = f'../working_file/file_for_mailing/{user_id}'

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT message, use_file FROM mailing WHERE id = ?", (user_id,))
    mailing_info = cursor.fetchone()  # возьмёт все имеющиеся строки
    connection.close()

    message_for_user += mailing_info[0]

    if mailing_info[1] == 1:
        if os.path.exists(directory) and os.path.isdir(directory):

            files = os.listdir(directory)  # Получаем список всех файлов в указанной папке

            for file in files:
                _, ext = os.path.splitext(file)  # Получаем расширение файла
                ext = ext.lower()  # Приводим расширение к нижнему регистру для удобства

                if ext in ['.jpg', '.jpeg', '.png', '.gif']:  # Проверяем, является ли файл изображением
                    message_for_user += '\n\nБудет использоваться прикреплённое к этому сообщению фото'

                    photo_path = f'../working_file/file_for_mailing/{user_id}/' + file

                    return [message_for_user, photo_path]
                else:
                    pass
        else:
            pass
    else:
        pass
    return [message_for_user, '']

async def edit_or_answer_message(chat_id: int, message_id: int, text: str, photo_path: str = None,
                                 reply_markup:  aiogram.utils.keyboard.InlineKeyboardMarkup = None)-> int:
    # возвращает id нового или изменённого сообщения

    try:
        if photo_path: # отсылаем сообщение с фото если это необходимо
            media = InputMediaPhoto(media=photo_path, caption=text, parse_mode="HTML")
            bot_message = await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media,
                                                       reply_markup=reply_markup, )
        else:
            bot_message = await bot.edit_message_text(chat_id=chat_id,message_id=message_id,text=text,
                                                      reply_markup= reply_markup,parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e): # если сообщение не изменено
            return message_id

        try: # удаляем сообщение
            await bot.delete_message(chat_id= chat_id,message_id=message_id)
        except TelegramBadRequest:
            pass

        if photo_path:
            bot_message = await bot.send_photo(chat_id=chat_id, caption=text, reply_markup=reply_markup,
                                                 photo=FSInputFile(photo_path),parse_mode='HTML')
        else:
            bot_message = await bot.send_message(chat_id=chat_id, text=text,reply_markup= reply_markup, parse_mode= "HTML")

    return bot_message.message_id


async def send_new_message(chat_id: int, text: str, photo_path: str = None,
                           reply_markup:  aiogram.utils.keyboard.InlineKeyboardMarkup = None)-> int:
    """"Если сообщение успешно отослано, то вернётся его ID"""
    try:
        if photo_path:
            bot_message = await bot.send_photo(chat_id=chat_id, caption=text, reply_markup=reply_markup,
                                                 photo=FSInputFile(photo_path),parse_mode='HTML')
        else:
            bot_message = await bot.send_message(chat_id=chat_id, text=text,reply_markup= reply_markup, parse_mode= "HTML")

        return bot_message.message_id
    except TelegramBadRequest:
        pass



