import asyncio
import sqlite3
import random
import string

from app.general_def import generate_captcha,get_conversion_rate, convert_rubles_to_dollars, get_info_user, show_message_for_all_mailing, edit_or_answer_message

from aiogram import F,Bot, Router # F добавляет обработчик на сообщения от пользователя (он будет принимать всё (картинки, стикеры, контакты))
from aiogram.filters import CommandStart, Command # CommandStart добавляет команду '/start'   Command добавляет команду которую мы сами можем придумать (ниже есть пример)
from aiogram.types import Message, CallbackQuery
from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext # для управления состояниями

import app.keyboards as kb # импортируем клавиатуру и сокращаем её на 'kb'

from config import TOKEN, CHANNEL_URL,CHANNEL_NAME, CRYSTAL_API_LOGIN, CRYSTAL_API_SECRETKEY1, CRYSTAL_API_SECRETKEY2

from crystalpay_sdk import CrystalPAY, PayoffSubtractFrom, InvoiceType # касса
crystalpayAPI = CrystalPAY(CRYSTAL_API_LOGIN, CRYSTAL_API_SECRETKEY1, CRYSTAL_API_SECRETKEY2)

bot = Bot(token = TOKEN)

router = Router() # это почти как диспетчер только для handlers

class Form(StatesGroup): # этот класс хранит в себе ответ пользователя на запрос ввести канал дял парсинга
    waiting_for_answer = State()
    captcha = State()
    ref_code = State()
    id_for_info = State()
    change_level = State()
    mailing_all_message = State()
    photo_for_mailing = State()
    add_admin = State()
    delete_admin = State()


@router.message(CommandStart())
async  def cmd_start(message: Message, state: FSMContext):
    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT id FROM users WHERE id = ?", (message.from_user.id,))
    result = cursor.fetchone()  # Извлекает первую найденную строку

    ref_id = message.text.split(maxsplit=1)# Получение аргумента реферального ID из команды
    if len(ref_id) > 1 and ref_id[1].isdigit():
        ref_id = int(ref_id[1])  # Преобразуем в целое число
        cursor.execute(f"SELECT id FROM users WHERE id = ?", (ref_id,))
        owner_id = cursor.fetchone()
        if not owner_id: # если НЕТ id которое указанно в реферальной ссылке
            ref_id = 0
    else: # если это не реф ссылка
        ref_id = 0

    connection.close()

    if result: # если уже зарегистрированы в боте
        await edit_or_answer_message(chat_id=message.from_user.id,message_id= 0,
                                     photo_path='../working_file/photo_for_message/start_message.png',
                                   text=f'Привет <b>{message.from_user.username}</b>!\nВаш id: <b>'
                                   f'{message.from_user.id}</b>\n\nВыберите пункт меню 👇',
                                   reply_markup = await kb.main_menu(message.from_user.id) )
    elif ref_id == 0:
        bot_message = await message.answer(
            f'Привет <b>{message.from_user.username}</b>!\n\nВы перешли не по реферальной ссылки.\nПожалуйста введите реферальный код для возможности пользоваться ботом',
            parse_mode="HTML")
        await state.update_data(bot_message_id=bot_message.message_id)  # Запоминаем message_id бота
        await state.set_state(Form.ref_code)
    else:
        captcha = generate_captcha(message.from_user.id, ref_id)
        bot_message = await message.answer(f'Перед началом использования бота необходимо пройти капчу\n\n<b>{captcha}</b>',
                                    parse_mode="HTML")
        await state.update_data(bot_message_id=bot_message.message_id)  # Запоминаем message_id бота
        await state.set_state(Form.captcha)  # устанавливаем состояние ожидания ответа

@router.message(Form.ref_code)
async def input_ref_code(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"]  # сообщение для удаления (это которое отослал бот)
    await state.clear()

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT id FROM users WHERE referral_code = ?", (message.text,))
    id_owner = cursor.fetchone()  # если есть такой реферальный код
    connection.close()

    try: # удаление сообщения пользователя
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    if id_owner:
        captcha = generate_captcha(message.from_user.id, id_owner[0])
        message_id = await edit_or_answer_message(chat_id = message.from_user.id,message_id = bot_message_id,
                                     text = f'Привет <b>{message.from_user.username}</b>!\n'
                                    f'Перед началом использования бота необходимо пройти капчу\n\n<b>{captcha}</b>')

        await state.update_data(bot_message_id=message_id)  # Запоминаем message_id бота
        await state.set_state(Form.captcha)  # устанавливаем состояние ожидания ответа
    else:
        message_id = await edit_or_answer_message(chat_id=message.from_user.id,
                                                  message_id=bot_message_id,
                                                  text=f'⚠️ <b>Введённый вами реферальный код не найден!</b>\n\n'
                                                       f'Пожалуйста введите ещё раз реферальный код для возможности пользоваться ботом',)

        await state.update_data(bot_message_id=message_id)  # Запоминаем message_id бота
        await state.set_state(Form.ref_code)

@router.message(Form.captcha)
async def captcha(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"]  # сообщение для удаления (это которое отослал бот)
    await state.clear()

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT answer, id_owner FROM captcha WHERE id = ?", (message.from_user.id,))
    from_db = cursor.fetchone()  # Извлекает первую найденную строку
    connection.close()

    try: # удаление сообщения пользователя
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    answer = 0

    try:
        answer = int(message.text)
    except ValueError:
        captcha = generate_captcha(message.from_user.id, 0)
        message_id = await edit_or_answer_message(chat_id=message.chat.id, message_id=bot_message_id,
                                                  text=f'⚠️ Введено некорректное значение, попытайтесь ещё раз\n\n<b>{captcha}</b>',)

        await state.update_data(bot_message_id=message_id)  # Запоминаем message_id бота
        await state.set_state(Form.captcha)
        return

    if answer == from_db[0]: # если ответ был правильным
        bot_info = await bot.get_me()

        while True:
            random_string = ''.join(random.choice(string.digits) for _ in range(5)) # генерируем рандомные числа (5 символов)
            random_string += ':'
            random_string += ''.join(random.choice(string.ascii_uppercase) for _ in range(5)) # генерируем рандомные буквы (5 символов)

            connection = sqlite3.connect('../working_file/data_base.sqlite3')
            cursor = connection.cursor()
            cursor.execute(f"SELECT referral_code FROM users WHERE referral_code = ?", (random_string,))
            referral_code = cursor.fetchone()  # Извлекает первую найденную строку
            connection.close()

            if referral_code: # если такой реферальный код уже есть
                pass
            else:
                break

        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()
        cursor.execute(f"INSERT INTO create_withdrawal (id) VALUES (?)",(message.from_user.id,))
        cursor.execute(f"INSERT INTO message_for_change (id) VALUES (?)",(message.from_user.id,))
        cursor.execute(f"INSERT INTO message_for_delete (id) VALUES (?)",(message.from_user.id,))
        cursor.execute(f"INSERT INTO users (id, user_name, owner_id, referral_url, referral_code) VALUES (?, ?, ?, ?, ?)",
                       (message.from_user.id,message.from_user.username, from_db[1],
                        f"https://t.me/{bot_info.username}?start={message.from_user.id}", random_string))
        cursor.execute(f'UPDATE message_for_delete SET message_id = ? WHERE id = ?', (0,message.from_user.id))
        connection.commit()  # сохранение
        connection.close()
        # проверка на подписку

        await edit_or_answer_message( chat_id = message.chat.id,message_id = bot_message_id,
                                 text = f'⚙️ Для получения доступа к ресурсу, пожалуйста, подпишитесь на '
                                f'Наш информационный канал и ознакомьтесь с пользовательским соглашением. (http://t.me/durov)',
                                reply_markup = kb.subscription_verification)
    else:
        captcha = generate_captcha(message.from_user.id, 0 )

        message_id = await edit_or_answer_message(chat_id = message.chat.id,message_id = bot_message_id,
                                 text = f'⚠️ Введено неверное значение, попытайтесь ещё раз\n\n<b>{captcha}</b>',)

        await state.update_data(bot_message_id=message_id)  # Запоминаем message_id бота
        await state.set_state(Form.captcha)
    connection.close()

@router.callback_query(F.data == 'subscription_verification')
async def subscription_verification(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    member = await bot.get_chat_member(chat_id=CHANNEL_NAME, user_id=callback.from_user.id)
    if member.status in ["left", "kicked"]:  # если пользователь не подписан на канал
        await callback.answer(f'Внимание!\nВы не подписаны на канал:\n\n{CHANNEL_URL}',show_alert = True,parse_mode= 'HTML')
    else:
        try:
            await bot.delete_message(chat_id=callback.from_user.id, message_id=callback.message.message_id)
        except TelegramBadRequest:  # если сообщение удалено
            pass

        await callback.answer('✅ Проверка подписки прошла успешно!',show_alert = False,parse_mode= 'HTML')

        new_message = await callback.message.answer('🕓 ЗАГРУЗКА: 10% / 100%\n[🟧️▫️️▫️️▫️️▫️️▫️️▫️️▫️️▫️️▫️]',)
        await asyncio.sleep(0.15)
        await new_message.edit_text('🕐 ЗАГРУЗКА: 20,32% / 100%\n[🟧🟧️️▫️️▫️️▫️️▫️️▫️️▫️️▫️️▫️]',)
        await asyncio.sleep(0.15)
        await new_message.edit_text('🕕 ЗАГРУЗКА: 30,85% / 100%\n[🟧🟧🟧️▫️▫️️▫️️▫️️▫️️▫️️▫️]')
        await asyncio.sleep(0.15)
        await new_message.edit_text('🕙 ЗАГРУЗКА: 40,76% / 100%\n[🟧🟧🟧🟧️▫️️▫️️▫️▫️▫️▫️]')
        await asyncio.sleep(0.15)
        await new_message.edit_text('🕓 ЗАГРУЗКА: 50,44% / 100%\n[🟧🟧🟧🟧🟧️️▫️▫️▫️️▫️️▫️]')
        await asyncio.sleep(0.15)
        await new_message.edit_text('🕜 ЗАГРУЗКА: 60,21% / 100%\n[🟧🟧🟧🟧🟧🟧️▫️️▫️️▫️️▫️]')
        await asyncio.sleep(0.15)
        await new_message.edit_text('🕟 ЗАГРУЗКА: 70,95% / 100%\n[🟧🟧🟧🟧🟧🟧🟧️▫️️▫️️▫️]')
        await asyncio.sleep(0.15)
        await new_message.edit_text('🕣 ЗАГРУЗКА: 80,54% / 100%\n[🟧🟧🟧🟧🟧🟧🟧🟧️▫️️▫️]')
        await asyncio.sleep(0.15)
        await new_message.edit_text('🕥 ЗАГРУЗКА: 90,03% / 100%\n[🟧🟧🟧🟧🟧🟧🟧🟧🟧️️▫️️]')
        await asyncio.sleep(0.15)
        await new_message.edit_text('🕧 ЗАГРУЗКА: 100% / 100%\n[🟧🟧🟧🟧🟧🟧🟧🟧🟧🟧]')
        await asyncio.sleep(0.15)
        await new_message.edit_text('Необходимо выбрать основную валюту в боте', reply_markup= kb.select_currency)
