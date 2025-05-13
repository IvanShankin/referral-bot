import os
import sqlite3
from datetime import datetime as dt
import shutil

from aiogram import F,Bot, Router
from aiogram.types import CallbackQuery
from aiogram import types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import FSInputFile
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext # для управления состояниями
from app.general_def import  get_info_user, show_message_for_all_mailing, edit_or_answer_message

import app.keyboards as kb # импортируем клавиатуру и сокращаем её на 'kb'

from config import TOKEN, ADMIN_CHAT_ID

router = Router() # это почти как диспетчер только для handlers

bot = Bot(token = TOKEN)
class Form(StatesGroup): # этот класс хранит в себе ответ пользователя
    id_for_create_order = State()
    sum_for_create_order = State()
    id_for_info = State()
    change_level = State()
    mailing_all_message = State()
    photo_for_mailing = State()
    add_admin = State()
    delete_admin = State()
    comment_on_refusal = State()

async def check_user_id(user_id: str)-> bool:
    """Вернёт True если пользователь с таким id есть"""
    # проверка
    try:
        user_id = int(user_id)
    except ValueError:
        return False # если не смогли преобразовать в int

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT id FROM users WHERE id = ?", (user_id,))
    test = cursor.fetchall()  # возьмёт все имеющиеся строки
    connection.close()

    if test:  # если пользователь с таким ID есть
        return True
    else:
        return False

@router.callback_query(F.data == 'admin_panel')
async def replenishment(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    message_id = await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                               text = f'Выберите необходимое действие 👇',reply_markup= kb.admin_panel)

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"UPDATE message_for_change SET message_id = ? WHERE id = ?", (message_id,callback.from_user.id))
    cursor.execute(f"UPDATE message_for_delete SET message_id = ? WHERE id = ?", (message_id,callback.from_user.id))
    connection.commit()
    connection.close()

@router.callback_query(F.data == 'orders')
async def orders(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text=f'Выберите действие с заявками 👇',reply_markup=kb.orders)

@router.callback_query(F.data == 'add_orders')
async def add_orders(callback: CallbackQuery, state: FSMContext):
    message_id = await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text=f'Введите ID пользователя для которого будет создана заявка:',
                                 reply_markup=kb.back_in_orders)
    await state.update_data(bot_message_id = message_id) # Запоминаем message_id бота
    await state.set_state(Form.id_for_create_order)

@router.message(Form.id_for_create_order)
async def id_for_create_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"] # сообщение для удаления (это которое отослал бот)
    await state.clear()

    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    test = await check_user_id(message.text)

    if test:
        message_id = await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,
                                                  text=f'Введите сумму для пополнения:',
                                                  reply_markup=kb.back_in_orders)
        await state.update_data(bot_message_id=message_id, user_id = message.text)  # Запоминаем message_id бота
        await state.set_state(Form.sum_for_create_order)
    else:
        message_id = await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,
                                                  text=f'Пользователь с таким ID не найден!\nПопробуйте ещё раз',
                                                  reply_markup=kb.back_in_orders)
        await state.update_data(bot_message_id=message_id)  # Запоминаем message_id бота
        await state.set_state(Form.id_for_create_order)

@router.message(Form.sum_for_create_order)
async def id_for_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"] # сообщение для удаления (это которое отослал бот)
    user_id = data["user_id"]
    await state.clear()

    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    try:
        sum_for_replenishment = int(message.text)
    except ValueError:
        message_id = await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,
                                                  text=f'Введена некорректная сумма!\nПопробуйте ввести ещё раз',
                                                  reply_markup=kb.back_in_orders)
        await state.update_data(bot_message_id=message_id, user_id=user_id)  # Запоминаем message_id бота
        await state.set_state(Form.sum_for_create_order)
        return

    current_datetime = dt.now()
    formatted_time = current_datetime.strftime("%H:%M:%S %d-%m-%Y")

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()

    cursor.execute(f"INSERT INTO replenishment_request "
                   f"(way,status,data_create,data_completion,sum,id_customer,id_admin) "
                   f"VALUES (?,?,?,?,?,?,?)", ('admin','completed',formatted_time, formatted_time,
                                               sum_for_replenishment, user_id, message.from_user.id)) # создание заявки

    cursor.execute(f"SELECT id FROM replenishment_request WHERE data_create = ? AND sum = ? AND id_customer = ?",
                   (formatted_time,sum_for_replenishment,user_id))
    id_order = cursor.fetchone() # узнаём id заявки

    cursor.execute(f"SELECT balance, user_name FROM users WHERE id = ?",
                   (user_id,))
    info_user = cursor.fetchone()  # узнаём какой баланс у пользователя которому хотим его пополнить

    new_balance = info_user[0] + sum_for_replenishment

    cursor.execute(f"UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
    connection.commit() # обновляем баланс

    connection.close()

    message_in_admin_chat = (f'Админ создал заявку на пополнение {sum_for_replenishment} RUB\n'
                             f'ID админа: {message.from_user.id}\n'
                             f'user_name админа: @{message.from_user.username}\n\n'
                             f'Данные о заявке на пополнение:\n'
                             f'ID заявки: {id_order[0]}\n'
                             f'Сумма: {sum_for_replenishment} RUB\n'
                             f'ID получателя: {user_id}\n'
                             f'user_name получателя: @{info_user[1]}')

    try: # вывод в сообщения в чат с админами
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=message_in_admin_chat)
    except TelegramForbiddenError:
        pass

    try:
        await  bot.send_message(chat_id= user_id,
                                text= f'На ваш счёт начислено {sum_for_replenishment} RUB\nТекущий баланс: {new_balance} RUB')
    except TelegramBadRequest:
        pass

    await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,
                                 text=f'✅ Заявка на пополнение успешно сформирована и деньги отосланы\n\n'
                                        f'Данные о заявке на пополнение:\n'
                                        f'ID заявки: {id_order[0]}\n'
                                        f'Сумма: {sum_for_replenishment} RUB\n'
                                        f'ID получателя: {user_id}\n'
                                        f'user_name получателя: @{info_user[1]}',
                                 reply_markup=kb.back_in_orders)

@router.callback_query(F.data == 'show_data')
async def show_info_user(callback: CallbackQuery, state: FSMContext):
    message_id = await edit_or_answer_message(chat_id=callback.from_user.id, message_id= callback.message.message_id,
                                 text= f'Введите ID пользователя\nдля просмотра информации о нём',
                                    reply_markup= kb.back_in_admin_panel)

    await state.update_data(bot_message_id = message_id) # Запоминаем message_id бота
    await state.set_state(Form.id_for_info)

@router.message(Form.id_for_info)
async def id_for_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"] # сообщение для удаления (это которое отослал бот)
    await state.clear()

    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    test = await check_user_id(message.text)

    if test: # если пользователь с таким ID есть
        message_id = await edit_or_answer_message(chat_id=message.chat.id,message_id=bot_message_id, text='Загрузка данных...', )

        message_info = get_info_user(int(message.text))

        await edit_or_answer_message(chat_id=message.chat.id,message_id=message_id,text=message_info,
                                     reply_markup=kb.back_in_admin_panel)
    else:
        message_id = await edit_or_answer_message(chat_id=message.chat.id,message_id=bot_message_id,
                                    text="⚠️ Пользователем с таким ID нет ⚠️\nпопытайтесь ещё раз",
                                    reply_markup=kb.back_in_admin_panel)

        await state.update_data(bot_message_id= message_id)  # Запоминаем message_id бота
        await state.set_state(Form.id_for_info)


@router.callback_query(F.data == 'change_level')
async def change_level(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    message_id = await edit_or_answer_message(chat_id=callback.from_user.id, message_id= callback.message.message_id,
                                              text="Введите ID пользователя",reply_markup=kb.back_in_admin_panel)

    await state.update_data(bot_message_id=message_id)  # Запоминаем message_id бота
    await state.set_state(Form.change_level)

@router.message(Form.change_level)
async def change_level(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"]  # сообщение для удаления (это которое отослал бот)
    await state.clear()

    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    test = await check_user_id(message.text) # проверка на наличие такого id

    if test: # если пользователь с таким ID есть

        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()
        cursor.execute(f"SELECT user_name, level FROM users WHERE id = ?", (int(message.text),))
        info_user = cursor.fetchone()
        connection.close()

        message_result = ''
        if info_user[1] == 4:
            message_result = (f'Выберите уровень для пользователя\n\nИмя пользователя: @{info_user[0]}\n'
            f'ID: {message.text}\nТекущий уровень: Партнёр')
        else:
            message_result = (f'Выберите уровень для пользователя\n\nИмя пользователя: @{info_user[0]}\n'
            f'ID: {message.text}\nТекущий уровень: {info_user[1]}')

        await edit_or_answer_message(chat_id=message.chat.id, message_id=bot_message_id, text=message_result,
                                    reply_markup= await kb.variants_levels(message.text))
    else:
        message_id = await edit_or_answer_message(chat_id=message.chat.id,message_id=bot_message_id,
                                    text="⚠️ Пользователем с таким ID нет ⚠️\nпопытайтесь ещё раз",
                                    reply_markup=kb.back_in_admin_panel)

        await state.update_data(bot_message_id= message_id)  # Запоминаем message_id бота
        await state.set_state(Form.change_level)

@router.callback_query(F.data.startswith('set_level_'))
async def set_level(callback: CallbackQuery):
    level = callback.data.split('_')[2]
    user_id = callback.data.split('_')[3]

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"UPDATE users SET level = ? WHERE id = ?", (int(level), int(user_id)))
    connection.commit()
    connection.close()

    if level == '4':
        level = 'Партнёр'

    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text=f"✅ Успешно установлен lvl {level}\nдля {user_id}",
                                 reply_markup=kb.back_in_admin_panel)

@router.callback_query(F.data == 'mailing_all_info')
async def mailing_all(callback: CallbackQuery):
    message_for_user = show_message_for_all_mailing(callback.from_user.id)

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT message_id FROM message_for_delete WHERE id = ?", (callback.from_user.id,))
    message_id_for_change = cursor.fetchone()
    connection.close()
    try:
        await bot.delete_message(chat_id=callback.from_user.id, message_id=message_id_for_change[0])
    except TelegramBadRequest:
        pass

    # если необходимо отослать фото (в первом элементе списка хранится путь к нему)
    if message_for_user[1]:
        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()

        try:
            bot_message = await callback.message.answer_photo(photo=FSInputFile(message_for_user[1]),caption=message_for_user[0],
                                                reply_markup=kb.mailing_all_info,parse_mode= 'HTML')
        except TelegramBadRequest: # может возникнуть ошибка из-за неправильного HTML синтаксиса
            bot_message = await callback.message.answer_photo(photo=FSInputFile(message_for_user[1]),
                                                     caption='⚠️ Внимание! \n\nНарушен <b>HTML</b> синтаксис!\nВведите сообщение ещё раз',
                                                     reply_markup=kb.mailing_all_info, parse_mode='HTML')
            cursor.execute(f"UPDATE mailing SET message = ? WHERE id = ?", (' ', callback.from_user.id))

        cursor.execute(f"UPDATE message_for_delete SET message_id = ? WHERE id = ?",
                       (bot_message.message_id, callback.from_user.id))
        connection.commit()
        connection.close()
    else:
        await callback.message.answer(text= message_for_user[0],reply_markup=kb.mailing_all_info,parse_mode= 'HTML')

@router.callback_query(F.data == 'mailing_confirmation')
async def mailing_all(callback: CallbackQuery):
    try:
        await bot.delete_message(chat_id=callback.from_user.id, message_id=callback.message.message_id)
    except TelegramBadRequest:
        pass
    bot_message = await callback.message.answer(f'Вы уверенны что хотите разослать\nсообщение всем пользователям бота?',
                                  reply_markup= kb.choice_for_mailing)

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"UPDATE message_for_delete SET message_id = ? WHERE id = ?",
                   (bot_message.message_id, callback.from_user.id))
    connection.commit()
    connection.close()

@router.callback_query(F.data == 'mailing_all')
async def mailing_all(callback: CallbackQuery):
    await edit_or_answer_message(chat_id=callback.from_user.id, message_id= callback.message.message_id,
                                 text=f"✅ Сообщение успешно разослано", reply_markup=kb.back_in_mailing_all)

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT id FROM users")
    all_users_id = cursor.fetchall()  # возьмёт все имеющиеся строки
    cursor.execute(f"SELECT message, use_file FROM mailing WHERE id = ?", (callback.from_user.id, ))
    mailing = cursor.fetchone()  # возьмёт первую строку
    connection.close()

    if mailing[1] == 1:  # если необходимо использовать фото для рассылки
        path_directory = f'../working_file/file_for_mailing/{callback.from_user.id}'
        path_photo = ''
        for item in os.listdir(path_directory):
            path_photo = os.path.join(path_directory, item) # формируем полный путь к фото

        for user_id in all_users_id:
            try:
                await bot.send_photo(photo=FSInputFile(path_photo),chat_id=user_id[0],caption=mailing[0],parse_mode='HTML')
            except Exception:
                pass
    else:
        for user_id in all_users_id:
            try:
                await bot.send_message(chat_id=user_id[0], text=mailing[0],parse_mode= 'HTML',)
            except Exception:
                pass

@router.callback_query(F.data == 'change_message')
async def change_message(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        bot_message = await callback.message.edit_text(text=f"Введите сообщение которое\nувидят все пользователи бота",
                                         reply_markup=kb.back_in_admin_panel)
    except TelegramBadRequest:
        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()
        cursor.execute(f"SELECT message_id FROM message_for_delete WHERE id = ?", (callback.from_user.id,))
        message_id_delete = cursor.fetchone()
        connection.close()
        try:
            await bot.delete_message(chat_id=callback.from_user.id, message_id=message_id_delete[0])
        except TelegramBadRequest:  # если сообщение удалено
            pass
        bot_message = await callback.message.answer(f'Введите сообщение которое\nувидят все пользователи бота',
                                      reply_markup=kb.back_in_mailing_all,parse_mode= 'HTML')

    await state.update_data(bot_message_id=bot_message.message_id)  # Запоминаем message_id бота
    await state.set_state(Form.mailing_all_message)


@router.message(Form.mailing_all_message)
async def mailing_all(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"]  # сообщение для удаления (это которое отослал бот)
    await state.clear()

    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"UPDATE mailing SET message = ? WHERE id = ?", (message.text, message.from_user.id))
    connection.commit()
    connection.close()

    message_for_user = show_message_for_all_mailing(message.from_user.id)

    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=bot_message_id)
    except TelegramBadRequest:
        pass

    # если необходимо отослать фото (в первом элементе списка хранится путь к нему)
    if message_for_user[1]:
        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()

        try:
            bot_message = await message.answer_photo(photo=FSInputFile(message_for_user[1]),caption=message_for_user[0],
                                                      reply_markup=kb.mailing_all_info, parse_mode='HTML')
        except TelegramBadRequest: # может возникнуть ошибка из-за неправильного HTML синтаксиса
            bot_message = await message.answer_photo(photo=FSInputFile(message_for_user[1]),
                                                     caption='⚠️ Внимание! \n\nНарушен <b>HTML</b> синтаксис!\nВведите сообщение ещё раз',
                                                     reply_markup=kb.mailing_all_info, parse_mode='HTML')
            cursor.execute(f"UPDATE mailing SET message = ? WHERE id = ?", (' ', message.from_user.id))

        cursor.execute(f"UPDATE message_for_delete SET message_id = ? WHERE id = ?",
                       (bot_message.message_id, message.from_user.id))
        connection.commit()
        connection.close()
    else:
        await message.answer(text=message_for_user[0], reply_markup=kb.mailing_all_info, parse_mode='HTML')


@router.callback_query(F.data == 'attach_file')
async def attach_file(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        bot_message = await callback.message.edit_text(text=f"Отошлите фото для сообщения\n\nОграничения:"
                                                            f"\nВозможно использовать только фото\nФото не более 50мб",
                                                       reply_markup=kb.back_in_mailing_all)
    except TelegramBadRequest:
        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()
        cursor.execute(f"SELECT message_id FROM message_for_delete WHERE id = ?", (callback.from_user.id,))
        message_id_delete = cursor.fetchone()
        connection.close()
        try:
            await bot.delete_message(chat_id=callback.from_user.id, message_id=message_id_delete[0])
        except TelegramBadRequest:  # если сообщение удалено
            pass
        bot_message = await callback.message.answer(f'Отошлите фото для сообщения\n\nОграничения:'
                                                    f'\nВозможно использовать только фото\nФото не более 50мб',
                                                    reply_markup=kb.back_in_mailing_all,parse_mode= 'HTML')

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"UPDATE message_for_delete SET message_id = ? WHERE id = ?",
                   (bot_message.message_id, callback.from_user.id))
    connection.commit()
    connection.close()

    await state.update_data(bot_message_id=bot_message.message_id)  # Запоминаем message_id бота
    await state.set_state(Form.photo_for_mailing)

@router.message(Form.photo_for_mailing)
async def photo_for_mailing(message: types.Message, state: FSMContext):
    message_for_user = ''
    this_photo = True

    data = await state.get_data()
    bot_message_id = data["bot_message_id"]  # сообщение для удаления (это которое отослал бот)
    await state.clear()

    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    if message.photo:
        file_info = message.photo[-1]
        file_type = "photo"
    elif message.document and message.document.mime_type.startswith('image/'):
        file_info = message.document
        file_type = "document"
    else:
        message_for_user += '️⚠️ Сообщение может содержать только фото!\n'
        file_info = message.text
        this_photo = False

    # Проверка размера файла
    max_size_bytes = 50 * 1024 * 1024 # максимальный размер файла 50мб (отображается в байтах)
    if this_photo and file_info.file_size > max_size_bytes:
        message_for_user += '️⚠️ Файл слишком большой! Максимальный размер: 50 МБ'
    elif this_photo: # если всё хорошо и можно сохранять фото
        # удаление файлом в папке админа
        try:
            # Получаем список всех файлов и подкаталогов в указанной папке
            for item in os.listdir(f'../working_file/file_for_mailing/{message.from_user.id}'):
                item_path = os.path.join(f'../working_file/file_for_mailing/{message.from_user.id}', item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)  # Удаляем файл
                    elif os.path.isdir(item_path):
                        os.rmdir(item_path)  # Удаляем пустую директорию
                except Exception:
                    pass

            # Получаем информацию о файле
            file = await bot.get_file(file_info.file_id)

            # Формируем путь для сохранения
            file_ext = file.file_path.split('.')[-1] if '.' in file.file_path else 'jpg' # преобразование в jpeg
            filename = f"{message.from_user.id}_{message.message_id}.{file_ext}"
            save_path = os.path.join(f'../working_file/file_for_mailing/{message.from_user.id}', filename) # сохранение

            # Скачиваем файл
            await bot.download_file(file.file_path, save_path)
            message_for_user += '️✅ Файл успешно сохранён'
            connection = sqlite3.connect('../working_file/data_base.sqlite3')
            cursor = connection.cursor()
            cursor.execute(f"UPDATE mailing SET use_file = ? WHERE id = ?", (1, message.from_user.id))
            connection.commit()
            connection.close()
        except Exception:
            message_for_user += '️⚠️ Ошибка!!!\n\nФото не сохранено!'

    message_id = await edit_or_answer_message(chat_id = message.from_user.id, message_id = bot_message_id,
                                          text=message_for_user,reply_markup=kb.back_in_mailing_all)

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"UPDATE message_for_delete SET message_id = ? WHERE id = ?",
                   (message_id, message.from_user.id))
    connection.commit()
    connection.close()


@router.callback_query(F.data == 'unpin_file')
async def unpin_file(callback: CallbackQuery):
    # Получаем список всех файлов и подкаталогов в указанной папке
    for item in os.listdir(f'../working_file/file_for_mailing/{callback.from_user.id}'):
        item_path = os.path.join(f'../working_file/file_for_mailing/{callback.from_user.id}', item)
        try:
            if os.path.isfile(item_path):
                os.remove(item_path)  # Удаляем файл
            elif os.path.isdir(item_path):
                os.rmdir(item_path)  # Удаляем пустую директорию
        except Exception:
            pass

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"UPDATE mailing SET use_file = ? WHERE id = ?",(0, callback.from_user.id))
    connection.commit()
    connection.close()

    await callback.answer('Фото успешно убрано!')

    message_for_user = show_message_for_all_mailing(callback.from_user.id)

    try:
        await bot.delete_message(chat_id=callback.from_user.id, message_id=callback.message.message_id)
    except TelegramBadRequest:
        pass

    # если необходимо отослать фото (в первом элементе списка хранится путь к нему)
    if message_for_user[1]:
        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()
        try:
            bot_message = await callback.message.answer_photo(photo=FSInputFile(message_for_user[1]),caption=message_for_user[0],
                                                      reply_markup=kb.mailing_all_info, parse_mode='HTML')
        except TelegramBadRequest: # может возникнуть ошибка из-за неправильного HTML синтаксиса
            bot_message = await callback.message.answer_photo(photo=FSInputFile(message_for_user[1]),
                                                     caption='⚠️ Внимание! \n\nНарушен <b>HTML</b> синтаксис!\nВведите сообщение ещё раз',
                                                     reply_markup=kb.mailing_all_info, parse_mode='HTML')
            cursor.execute(f"UPDATE mailing SET message = ? WHERE id = ?", (' ', callback.from_user.id))

        cursor.execute(f"UPDATE message_for_delete SET message_id = ? WHERE id = ?",
                       (bot_message.message_id, callback.from_user.id))
        connection.commit()
        connection.close()
    else:
        await callback.message.answer(text=message_for_user[0], reply_markup=kb.mailing_all_info, parse_mode='HTML')



@router.callback_query(F.data == 'add_admin')
async def add_admin(callback: CallbackQuery, state: FSMContext):

    message_id = await edit_or_answer_message(chat_id=callback.from_user.id, message_id= callback.message.message_id,
                                              text=f"Введите id пользователя которого хотите сделать админом\n\n"
                                              f"примечание: пользователь должен быть зарегистрирован в боте",
                                              reply_markup=kb.back_in_admin_panel)

    await state.update_data(bot_message_id= message_id)  # Запоминаем message_id бота
    await state.set_state(Form.add_admin)

@router.message(Form.add_admin)
async def add_admin(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"]  # сообщение для удаления (это которое отослал бот)
    await state.clear()

    message_result = ''

    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    try:
        user_id = int(message.text)
    except ValueError:
        message_result = '⚠️ Введён некорректный ID ⚠️\nпопытайтесь ещё раз\n'
        user_id = 0

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT id FROM users WHERE id = ?", (user_id,))
    info_user = cursor.fetchone()
    cursor.execute(f"SELECT admin_id FROM admins WHERE admin_id = ?", (user_id,))
    user_is_admin = cursor.fetchone()
    connection.close()
    if info_user: # если пользователь с таким ID есть

        if user_is_admin:
            message_result += '⚠️ Пользователь уже является админом'
        else:
            new_directory_admin = os.path.join('../working_file/file_for_mailing', str(user_id))
            os.makedirs(new_directory_admin, exist_ok=True) # создание папки для админа

            connection = sqlite3.connect('../working_file/data_base.sqlite3')
            cursor = connection.cursor()
            cursor.execute(f"INSERT INTO mailing (id) VALUES (?)",(user_id,))
            cursor.execute(f"INSERT INTO admins (admin_id) VALUES (?)",(user_id,))
            connection.commit()  # сохранение
            connection.close()

            await edit_or_answer_message(chat_id=message.chat.id, message_id=bot_message_id,
                                        text='✅ Успешно установлен статус админа',reply_markup= kb.back_in_admin_panel)

            return
    else:
        message_result += '⚠️ Пользователем с таким ID нет ⚠️\nпопытайтесь ещё раз'

    message_id = await edit_or_answer_message(chat_id=message.chat.id,message_id=bot_message_id,text=message_result,
                                reply_markup=kb.back_in_admin_panel)

    await state.update_data(bot_message_id= message_id)  # Запоминаем message_id бота
    await state.set_state(Form.add_admin)

@router.callback_query(F.data == 'delete_admin')
async def delete_admin(callback: CallbackQuery, state: FSMContext):
    message_id = await edit_or_answer_message(chat_id=callback.from_user.id, message_id= callback.message.message_id,
                                              text=f"Введите id пользователя у которого хотите убрать статус админ",
                                             reply_markup=kb.back_in_admin_panel)

    await state.update_data(bot_message_id=message_id)  # Запоминаем message_id бота
    await state.set_state(Form.delete_admin)

@router.message(Form.delete_admin)
async def delete_admin(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"]  # сообщение для удаления (это которое отослал бот)
    await state.clear()

    message_result = ''

    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    try:
        user_id = int(message.text)
    except ValueError:
        message_result = '⚠️ Введён некорректный ID ⚠️\nпопытайтесь ещё раз\n'
        user_id = 0

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT id FROM users WHERE id = ?", (user_id,))
    info_user = cursor.fetchone()
    cursor.execute(f"SELECT admin_id FROM admins WHERE admin_id = ?", (user_id,))
    user_is_admin = cursor.fetchone()
    connection.close()
    if info_user: # если пользователь с таким ID есть

        if user_is_admin:

            directory_admin = os.path.join('../working_file/file_for_mailing', str(user_id))
            shutil.rmtree(directory_admin)

            connection = sqlite3.connect('../working_file/data_base.sqlite3')
            cursor = connection.cursor()
            cursor.execute(f'DELETE FROM mailing WHERE id = ?', (user_id,))
            cursor.execute(f'DELETE FROM admins WHERE admin_id = ?', (user_id,))
            connection.commit()  # сохранение
            connection.close()

            await edit_or_answer_message(chat_id=message.chat.id, message_id=bot_message_id,
                                        text='✅ Успешно убран статус админа',
                                        reply_markup=kb.back_in_admin_panel)
            return
        else:
            message_result += '⚠️ Пользователь не является админом'
    else:
        message_result += '⚠️ Пользователем с таким ID нет ⚠️\nпопытайтесь ещё раз'

    message_id = await edit_or_answer_message(chat_id=message.chat.id,message_id=bot_message_id,text=message_result,
                                reply_markup=kb.back_in_admin_panel)

    await state.update_data(bot_message_id=message_id)  # Запоминаем message_id бота
    await state.set_state(Form.delete_admin)

@router.callback_query(F.data == 'my_orders_withdrawal')
async def my_orders_withdrawal(callback: CallbackQuery, state: FSMContext):
    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text=f'Здесь отображены все заявки на вывод которые вы приняли 👇\n'
                                      f'Нажмите на заявку что бы просмотреть информацию о ней',
                                 reply_markup= await kb.all_orders())

@router.callback_query(F.data.startswith('show_order|'))
async def select_currency(callback: CallbackQuery):
    id_order = callback.data.split('|')[1]

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT sum, data_create, bank, phone_or_number_card, id_customer, status FROM withdrawal_requests WHERE id = ?",
                   (id_order,))
    order = cursor.fetchone()  # Извлекает все найденную строку
    connection.close()

    if order[5] != 'not_completed':
        await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'✅ Данная заявка уже обработана!',reply_markup=kb.back_in_orders)
        return 

    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text=f'Данные:\n'
                                      f'ID получателя: /user_id_{order[4]}\n'
                                      f'Дата создания: {order[1]}\n'
                                      f'Статус: не выполнено\n\n'
                                      f'💸 Сумма: <code>{order[0]}</code>\n'
                                      f'🏛️ Банк: {order[2]}\n'
                                      f'💳 Реквизиты: <code>{order[3]}</code>\n'
                                      f'Выберите действие над заявкой 👇',
                                 reply_markup=await kb.info_order(id_order))

@router.callback_query(F.data.startswith('confirm_output|'))
async def select_currency(callback: CallbackQuery):
    id_order = callback.data.split('|')[1]

    current_datetime = dt.now()
    formatted_time = current_datetime.strftime("%H:%M:%S %d-%m-%Y")

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()

    cursor.execute(f"SELECT sum,id_customer FROM withdrawal_requests WHERE id = ?", (id_order,))
    info_order = cursor.fetchone()  # Извлекает первую найденную строку

    cursor.execute(f"SELECT balance,withdrawal_balance FROM users WHERE id = ?", (info_order[1],))
    info_user = cursor.fetchone()  # Извлекает первую найденную строку

    sum_with_interest = (info_order[0] * 3) / 100  # сумма которую необходимо вычесть для подсчёта процента
    sum_with_interest = info_order[0] - sum_with_interest  # сумма на вывод с учётом комиссии

    new_balance = info_user[0] - info_order[0]
    new_withdrawal_balance = info_user[1] - info_order[0]

    cursor.execute(f"UPDATE users SET  balance = ?, withdrawal_balance = ? WHERE id = ?",
                   (new_balance, new_withdrawal_balance, info_order[1]))
    cursor.execute(f"UPDATE withdrawal_requests SET status = ?, data_completion = ? WHERE id = ?",
                   ('completed', formatted_time, id_order))
    connection.commit()

    connection.close()

    try:
        await bot.send_message(chat_id=info_order[1], text=f'💸 Деньги успешно выведены: {sum_with_interest}RUB',)
    except TelegramBadRequest:
        pass

    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'✅ Заявка успешно подтверждена\n'
                                          f'Заявка на {sum_with_interest}RUB выполнена',
                                     reply_markup= await kb.all_orders())

@router.callback_query(F.data.startswith('reject_output|'))
async def select_currency(callback: CallbackQuery, state: FSMContext):
    id_order = callback.data.split('|')[1]

    message_id = await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                              text='Напишите причину отказа (Это в будет отослано пользователю)',
                                              reply_markup=kb.back_in_orders)

    await state.update_data(bot_message_id=message_id, id_order = id_order)  # Запоминаем message_id бота
    await state.set_state(Form.comment_on_refusal)

@router.message(Form.comment_on_refusal)
async def comment_on_refusal(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"]
    id_order = data["id_order"]
    await state.clear()

    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    current_datetime = dt.now()
    formatted_time = current_datetime.strftime("%H:%M:%S %d-%m-%Y")

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()

    cursor.execute(f"SELECT id_customer, sum FROM withdrawal_requests WHERE id = ?", (id_order,))
    info_order = cursor.fetchone()

    cursor.execute(f"SELECT withdrawal_balance FROM users WHERE id = ?", (info_order[0],))
    withdrawal_balance = cursor.fetchone()  # Извлекает первую найденную строку

    new_withdrawal_balance = withdrawal_balance[0] - info_order[1]

    cursor.execute(f"UPDATE users SET withdrawal_balance = ? WHERE id = ?",
                   (new_withdrawal_balance, info_order[0]))

    cursor.execute(f"UPDATE withdrawal_requests SET status = ?, data_completion = ?, comment_on_refusal = ?  WHERE id = ?",
                   ('rejected',formatted_time,message.text, id_order))
    connection.commit()
    connection.close()

    try:
        await bot.send_message(chat_id=info_order[0],
                               text=f'Заявка №{id_order} на вывод была отклонена\n\n'
                                    f'Причина: {message.text}\n\n'
                                    f'Для получения больше информации обратитесь к менеджеру',
                               reply_markup= kb.manager_url)
    except TelegramBadRequest:
        pass

    await state.clear()
    await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,
                                  text=f'✅ Заявка успешно отклонена\n\nСообщение отправлено пользователю:\n{message.text}',
                                  reply_markup=await kb.all_orders())


@router.message(F.text.startswith("/order_id_"))
async def order_id(message: types.Message):
    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT admin_id FROM admins WHERE admin_id = ?", (message.from_user.id,))
    check_admin = cursor.fetchone()
    connection.commit()

    if check_admin: # если есть админ с таким id
        order_id = message.text.split("_")[2].strip()

        if not order_id.isdigit(): # если получили строку вместо числа
            return

        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()
        cursor.execute(f"SELECT id_customer,data_create, data_completion, sum, phone_or_number_card, bank, status, comment_on_refusal"
                       f" FROM withdrawal_requests WHERE id = ?",(order_id,))
        order = cursor.fetchone()
        connection.close()

        if order:
            connection = sqlite3.connect('../working_file/data_base.sqlite3')
            cursor = connection.cursor()
            cursor.execute(f"SELECT user_name FROM users WHERE id = ?",(order[0],))
            user_name = cursor.fetchone()
            connection.close()

            if not order[2]: # если нет даты завершения
                order[2] = 'не завершён'

            status = 'не выполнен'
            if order[6] == 'completed':
                status = 'выполнен'
            elif order[6] == 'rejected':
                status = f'отклонён \nПричина отклонения: {order[7]}'


            await message.answer(text=f'ID заявки:  /order_id_{order_id}_\n\n'
                                        f'ID пользователя:  /user_id_{order[0]}_\n'
                                        f'user_name пользователя: @{user_name[0]}\n\n'
                                        f'Дата создания: {order[1]}\n'
                                        f'Дата завершения: {order[2]}\n'
                                        f'Статус: <b>{status}</b>\n'
                                        f'💸 Сумма: <code>{order[3]}</code>\n'
                                        f'💳 Реквизиты: <code>{order[4]}</code>\n'
                                        f'🏛️ Банк: {order[5]}\n', parse_mode= 'HTML')
        else:
            await message.answer(f'❌ Заявки с ID = {order_id} нет!')


@router.message(F.text.startswith("/user_id_"))
async def order_id(message: types.Message):
    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT admin_id FROM admins WHERE admin_id = ?", (message.from_user.id,))
    check_admin = cursor.fetchone()
    connection.commit()

    if check_admin: # если есть админ с таким id
        user_id = message.text.split("_")[2].strip()

        if not user_id.isdigit(): # если получили строку вместо числа
            return

        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()
        cursor.execute(f"SELECT id FROM users WHERE id = ?", (user_id,))
        check_user = cursor.fetchone()
        connection.close()

        if check_user: # если такой пользователь есть
            text = get_info_user(int(user_id))
            await message.answer(text)
        else:
            await message.answer(f'❌ Пользователя с ID = {user_id} нет')


