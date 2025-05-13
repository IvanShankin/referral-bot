import sqlite3

from app.general_def import edit_or_answer_message

from aiogram import F,Bot, Router, types
from aiogram.types import CallbackQuery

import app.keyboards as kb # импортируем клавиатуру и сокращаем её на 'kb'

from config import TOKEN


router = Router() # это почти как диспетчер только для handlers

bot = Bot(token = TOKEN)

@router.callback_query(F.data == 'info')
async def select_currency(callback: CallbackQuery):
    await edit_or_answer_message(callback.from_user.id, callback.message.message_id, text='тут информация',
                                 reply_markup= kb.back_in_main_menu)

@router.callback_query(F.data == 'settings')
async def select_currency(callback: CallbackQuery):
    await edit_or_answer_message(callback.from_user.id, callback.message.message_id, text='⚙️ Настройки',
                                 reply_markup=await kb.settings(callback.from_user.id))

@router.callback_query(F.data.startswith('change_currency_'))
async def select_currency(callback: CallbackQuery):
    currency = callback.data.split('_')[2]

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"UPDATE users SET selected_currency = ? WHERE id = ?", (currency, callback.from_user.id))
    connection.commit()
    connection.close()

    await edit_or_answer_message(callback.from_user.id, callback.message.message_id, text= '⚙️ Настройки',
                                 reply_markup=await kb.settings(callback.from_user.id))


@router.callback_query(F.data == 'notification_replenishment')
async def select_currency(callback: CallbackQuery):
    await edit_or_answer_message(callback.from_user.id, callback.message.message_id,
                                 text='⚙️ Выберите от рефералов каких ступеней вы будите получать уведомления о пополнении',
                                 reply_markup=await kb.notification_replenishment(callback.from_user.id))

@router.callback_query(F.data.startswith('change_notification_stage|'))
async def select_currency(callback: CallbackQuery):
    stage = int(callback.data.split('|')[1]) # стадия для редактирования
    new_record = int(callback.data.split('|')[2]) # необходимое значение для БД

    if stage == 1:
        column_in_db = 'notifications_from_one_stage_referral'
    elif stage == 2:
        column_in_db = 'notifications_from_two_stage_referral'
    else:
        column_in_db = 'notifications_from_three_stage_referral'

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f'UPDATE users SET {column_in_db} = ? WHERE id = ?', (new_record, callback.from_user.id))
    connection.commit()
    connection.close()

    await edit_or_answer_message(callback.from_user.id, callback.message.message_id,
                                 text='⚙️ Выберите от рефералов каких ступеней вы будите получать уведомления о пополнении',
                                 reply_markup=await kb.notification_replenishment(callback.from_user.id))