import asyncio
import sqlite3
import re

from app.general_def import get_info_user, edit_or_answer_message

from datetime import datetime as dt
from aiogram import F,Bot, Router, types
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext # для управления состояниями

import app.keyboards as kb # импортируем клавиатуру и сокращаем её на 'kb'

from config import TOKEN, BOT_URL, CRYSTAL_API_LOGIN, CRYSTAL_API_SECRETKEY1, CRYSTAL_API_SECRETKEY2, CRYPTO_TOKEN, ADMIN_CHAT_ID

from crystalpay_sdk import CrystalPAY, InvoiceType # касса
crystalpayAPI = CrystalPAY(CRYSTAL_API_LOGIN, CRYSTAL_API_SECRETKEY1, CRYSTAL_API_SECRETKEY2)

from aiocryptopay import AioCryptoPay, Networks # КБ
crypto = AioCryptoPay(token=CRYPTO_TOKEN, network=Networks.TEST_NET) # КБ

router = Router() # это почти как диспетчер только для handlers

bot = Bot(token = TOKEN)

class Form(StatesGroup): # этот класс хранит в себе ответ пользователя
    replenishment_or_withdrawal = State()
    phone_or_number_card = State()
    bank = State()
    spb = State()
    another_bank = State()
    number_card = State()
    number_phone = State()

def is_possible_phone_number(phone: str) -> bool:
    # Удаляем всё, кроме цифр и "+" (если он в начале)
    cleaned = re.sub(r"[^\d+]", "", phone)

    # Проверяем, что остались только цифры (или + в начале)
    if not re.fullmatch(r"\+?\d{10,15}", cleaned):
        return False

    # Доп. проверка: если есть "+", то после него должно быть 11-15 цифр
    if "+" in cleaned:
        return len(cleaned) >= 12  # +79161234567 → 12 символов
    else:
        return len(cleaned) >= 10  # 9161234567 → 10 цифр

# ожидает заданное время и ставит статус не выполнено если запрос на пополнение не оплачен
async def update_request_replenishment(order_id: int, waiting_time_in_seconds: int = 1800,):
    # по умолчанию 30 минут ожидания
    await asyncio.sleep(waiting_time_in_seconds)
    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT status FROM replenishment_request WHERE id = ?", (order_id,))
    order_status = cursor.fetchone()
    connection.close()

    if order_status[0] == 'not_completed': # установим что платёж отклонён
        current_datetime = dt.now()
        formatted_time = current_datetime.strftime("%H:%M:%S %d-%m-%Y")

        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()
        cursor.execute(f"UPDATE replenishment_request SET status = ?,data_completion = ?  WHERE id = ?",
                       ('rejected', formatted_time, order_id))
        connection.commit()
        connection.close()

@router.callback_query(F.data.startswith('selected_currency_'))
async def select_currency(callback: CallbackQuery):
    currency = callback.data.split('_')[2]

    await callback.answer('Валюта успешно установленна', show_alert=False,parse_mode= 'HTML')

    await edit_or_answer_message(photo_path='../working_file/photo_for_message/start_message.png',
                                 chat_id= callback.from_user.id,message_id=callback.message.message_id,
                                 text = f'Привет <b>{callback.from_user.username}</b>!\nВаш id: <b>'
                                     f'{callback.from_user.id}</b>\n\nВыберите пункт меню 👇',
                                     reply_markup=await kb.main_menu(callback.from_user.id))

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"UPDATE users SET selected_currency = ? WHERE id = ?",(currency, callback.from_user.id))
    connection.commit()
    connection.close()


@router.callback_query(F.data == 'main_menu')
async def select_currency(callback: CallbackQuery):
    await edit_or_answer_message(photo_path='../working_file/photo_for_message/start_message.png',
                                chat_id=callback.from_user.id, message_id= callback.message.message_id,
                                text = f'Привет <b>{callback.from_user.username}</b>!\nВаш id: <b>'
                                 f'{callback.from_user.id}</b>\n\nВыберите пункт меню 👇',
                                reply_markup = await kb.main_menu(callback.from_user.id))

@router.callback_query(F.data == 'profile')
async def profile(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    message_text = get_info_user(callback.from_user.id)
    await edit_or_answer_message(photo_path= '../working_file/photo_for_message/profile.png',chat_id= callback.from_user.id,message_id=callback.message.message_id,
                                text = message_text,reply_markup= kb.profile_keb)

@router.callback_query(F.data.startswith('money_'))
async def replenishment(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    choice = callback.data.split('_')[1]
    message_id = await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text=f'Введите сумму в рублях\n\nМинимум на пополнение: 100руб.\nМинимум на вывод: 500руб.',
                                              reply_markup= kb.back_in_profile)

    await state.update_data(choice = choice,bot_message_id = message_id )
    await state.set_state(Form.replenishment_or_withdrawal)

@router.message(Form.replenishment_or_withdrawal)
async def id_for_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"]  # сообщение для удаления (это которое отослал бот)
    choice = data["choice"]
    await state.clear()

    try: # удаление сообщения пользователя
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    try:
        selected_sum = int(message.text)
    except ValueError:
        await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,
                                     text=f'⚠️ Введите корректную сумму!', reply_markup= kb.back_in_profile)
        await state.update_data(choice=choice, bot_message_id=bot_message_id)
        await state.set_state(Form.replenishment_or_withdrawal)
        return

    message_error = ''
    if selected_sum < 100 or selected_sum > 10000:
        message_error = ('⚠️ \n\nМинимальная сумма пополнения 100руб!\nМинимальная сумма вывода 500руб!\n'
                         'Максимальная сумма 10000руб!')
    else:
        if choice == 'replenishment': # пополнение
            await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,
                                         text=f'Выберите метод пополнения 👇',
                                         reply_markup=await kb.replenishment())
            connection = sqlite3.connect('../working_file/data_base.sqlite3')
            cursor = connection.cursor()
            cursor.execute(f"UPDATE create_withdrawal SET selected_sum = ? WHERE id = ?",(selected_sum, message.from_user.id))
            connection.commit()
            connection.close()
            return
        elif choice == 'withdrawal': # вывод
            connection = sqlite3.connect('../working_file/data_base.sqlite3')
            cursor = connection.cursor()
            cursor.execute(f"SELECT balance, withdrawal_balance FROM users WHERE id = ?", (message.from_user.id,))
            balances = cursor.fetchone()
            connection.close()

            if balances[0] < selected_sum:
                message_error = '⚠️ Внимание!\n\nВаш баланс меньше желаемого вывода!'
            elif selected_sum < 500:
                message_error = '⚠️ Внимание!\n\nМинимальная сумма вывода 500руб!'
            elif (balances[0] - balances[1]) < selected_sum:
                message_error = ('⚠️ Внимание!\n\nУ вас достаточно денег на счету, но уже есть заявка на вывод и'
                                 ' указанная сумма превышает оставшийся баланс!\n\nДождитесь выполнения заявки или отмените её')
            else:
                await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,
                                             text=f'Выберите метод вывода 👇\n\nВнимание!\nПри выводе будет взиматься комиссия в 3%',
                                             reply_markup=await kb.withdrawal())
                connection = sqlite3.connect('../working_file/data_base.sqlite3')
                cursor = connection.cursor()
                cursor.execute(f"UPDATE create_withdrawal SET selected_sum = ? WHERE id = ?", (selected_sum, message.from_user.id))
                connection.commit()
                connection.close()
                return

    await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,text=message_error,
                                 reply_markup= kb.back_in_profile )
    await state.update_data(choice=choice, bot_message_id=bot_message_id)
    await state.set_state(Form.replenishment_or_withdrawal)
    return


@router.callback_query(F.data == 'history_transactions')
async def history_transactions(callback: CallbackQuery):
    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text='Выберите какую историю хотите просмотреть 👇',
                                 reply_markup=kb.transaction_history)

@router.callback_query(F.data == 'history_profit')
async def history_profit(callback: CallbackQuery):
    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text='Это история прибыли от ваших рефералов\nВыберите конкретную операцию\n\n'
                                      'Внимание! \nотображаются последние 100 пополнений',
                                 reply_markup=await kb.history_replenishment(callback.from_user.id,'profit_from_referrals'))

@router.callback_query(F.data == 'history_replenishment')
async def history_replenishment(callback: CallbackQuery):
    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text= 'Это история пополнения вашего счёта\nВыберите конкретную операцию\n\n'
                                       'Внимание! \nотображаются последние 100 пополнений',
                                reply_markup=await kb.history_replenishment(callback.from_user.id,'replenishment_request'))

@router.callback_query(F.data == 'history_withdrawal')
async def history_withdrawal(callback: CallbackQuery):
    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text='Это история вывода вашего счёта\nВыберите конкретную операцию\n\n'
                                      'Внимание! \nотображаются последние 100 пополнений',
                                 reply_markup=await kb.history_replenishment(callback.from_user.id,'withdrawal_requests'))

@router.callback_query(F.data.startswith('show_order_for_user|'))
async def show_order_for_user(callback: CallbackQuery):
    table = callback.data.split('|')[1]
    id_order = int(callback.data.split('|')[2])

    message_text = ''
    message_button = None # кнопки прикреплённые к сообщению

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()

    if table == 'replenishment_request':
        cursor.execute(f"SELECT status, way, data_create, data_completion, sum, url, id_payment"
                       f"  FROM replenishment_request WHERE id = ?", (id_order,))
        order_info = cursor.fetchone()

        status = ''
        method = ''
        data_completion = ''
        if order_info[0] == 'not_completed':
            status = 'не оплачен'
        elif order_info[0] == 'completed':
            status = 'оплачен'
        elif order_info[0] == 'rejected':
            status = 'время оплаты истекло'

        if order_info[1] == 'admin':
            method = 'через менеджера'
        elif order_info[1] == 'crystalPAY':
            method = 'криптовалюта (crystalPAY)'
        elif order_info[1] == 'cryptoBot':
            method = 'cryptoBot'

        if not order_info[3]:
            data_completion = 'не окончен'
        else:
            data_completion = order_info[3]

        message_text = (f'Заявка №{id_order}\n\n'
                        f'Сумма: {order_info[4]}\n'
                        f'Статус: {status}\n'
                        f'Метод: {method}\n'
                        f'Дата создания: {order_info[2]}\n'
                        f'Дата окончания: {data_completion}\n')

        if order_info[1] != 'admin': # это заявки, которые обрабатываются не через менеджера, а через crystalPAY или cryptoBot
            if order_info[0] == 'not_completed':
                message_button = await kb.payment_verification(order_info[1],id_order,order_info[6], order_info[5],
                                                               'history_replenishment' )
            else:
                message_button = kb.back_in_history_replenishment
        else: # для оплаты через менеджера
            message_button = await kb.payment_manager(back_button = 'history_replenishment')

    elif table == 'withdrawal_requests':
        cursor.execute(f"SELECT status, way, data_create, data_completion, sum, bank, phone_or_number_card, comment_on_refusal "
                       f"  FROM withdrawal_requests WHERE id = ?", (id_order,))
        order_info = cursor.fetchone()

        status = ''
        method = ''
        comment_on_refusal = ''
        bank = ''
        data_completion = ''
        if order_info[0] == 'not_completed':
            status = 'на обработке у менеджера'
        elif order_info[0] == 'completed':
            status = 'выведены'
        elif order_info[0] == 'rejected':
            status = 'отклонено'

        if not order_info[3]:
            data_completion = 'не окончен'
        else:
            data_completion = order_info[3]

        if order_info[5]:
            if order_info[5] == 'sber':
                bank = 'Банк: Сбербанк\n'
            elif order_info[5] == 'alpha':
                bank = 'Банк: Альфа\n'
            elif order_info[5] == 'Tbank':
                bank = 'Банк: Т банк\n'
            elif order_info[5] == 'vtb':
                bank = 'Банк: ВТБ\n'
            elif order_info[5] == 'ozon':
                bank = 'Банк: Озон\n'
            else:
                bank = order_info[5] + '\n'

        if order_info[7]:
            comment_on_refusal = f'\nКомментарий отказа: {order_info[7]}'


        message_text = (f'Заявка №{id_order}\n\n'
                        f'Сумма: {order_info[4]}\n'
                        f'Статус: {status}\n'
                        f'{bank}'
                        f'Реквизиты: {order_info[6]}\n'
                        f'Метод: через менеджера\n'
                        f'Дата создания: {order_info[2]}\n'
                        f'Дата окончания: {data_completion}'
                        f'{comment_on_refusal}')

        message_button = await kb.payment_manager(back_button = 'history_withdrawal')

    elif table == 'profit_from_referrals':
        cursor.execute(f"SELECT sum, id_referral, step_referral, return_percentage, date FROM profit_from_referrals WHERE id = ?",
                       (id_order,))
        order_info = cursor.fetchone()

        cursor.execute(f"SELECT user_name FROM users WHERE id = ?",(order_info[1],))
        referral_info = cursor.fetchone()


        if referral_info[0]: # если есть user_name
            user_name_referral = f'user_name реферала: @{referral_info[0]}'
        else:
            user_name_referral = f'id реферала: {order_info[1]}'


        message_text = (f'Заявка №{id_order}\n\n'
                        f'Сумма: {order_info[0]}\n'
                        f'{user_name_referral}\n'
                        f'Дата: {order_info[4]}\n'
                        f'Ступень реферала: {order_info[2]}\n'
                        f'Процент возврата: {order_info[3]}%')

        message_button = kb.back_in_history_profit

    connection.close()
    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text=message_text,reply_markup=message_button)

@router.callback_query(F.data.startswith('replenishment_'))
async def replenishment(callback: CallbackQuery):
    way = callback.data.split('_')[1]

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT selected_sum FROM create_withdrawal WHERE id = ?", (callback.from_user.id,))
    selected_sum = cursor.fetchone()
    connection.close()

    current_datetime = dt.now()
    formatted_time = current_datetime.strftime("%H:%M:%S %d-%m-%Y")

    if selected_sum[0] < 100:
        await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'⚠️ Минимальная сумма пополнения 100руб!',
                                     reply_markup=kb.back_in_profile)
        return

    if way == 'bankMap':
        await edit_or_answer_message(chat_id= callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'💳 Для выдачи реквизитов на оплату необходимо обратиться к менеджеру\n'
                                          f'Нажмите кнопку ниже и вставьте это сообщение:\n\n'
                                          f'<code>Здравствуйте, я хочу пополнить счёт на {selected_sum[0]}'
                                          f' мой id {callback.from_user.id}</code>',
                                     reply_markup=await kb.payment_manager())

    elif way == 'crystalPAY':
        invoice = crystalpayAPI.Invoice.create(
            amount=selected_sum[0],
            type_=InvoiceType.purchase,
            lifetime=30,  # 30 минут лимит ссылки
            description="Пополнение счёта у бота", # дописать
            currency= "RUB",
            redirect_url= BOT_URL  # Ссылка после оплаты
        )

        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()
        cursor.execute(f"INSERT INTO replenishment_request (id_payment,way,data_create,sum,url,id_customer) VALUES (?, ?, ?, ?, ?, ?)",
                       (invoice['id'],'crystalPAY', str(formatted_time), selected_sum[0],invoice['url'], callback.from_user.id))
        connection.commit()  # сохранение
        cursor.execute(f"SELECT id FROM replenishment_request WHERE id_payment = ? AND status = ?",
                       (invoice['id'],'not_completed'))
        order_id = cursor.fetchone()
        connection.close()

        await edit_or_answer_message(chat_id= callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'💳 Для оплаты нажмите кнопку ниже\n\nСчет действителен 30 минут',
                                     reply_markup= await kb.payment_verification('crystalPAY',
                                                                    order_id[0],invoice['id'],invoice['url']))

        await update_request_replenishment(order_id[0])
        # здесь вызов функции описанной в txt файле
    elif way == 'cryptoBot':
        fiat_invoice = await crypto.create_invoice(amount=selected_sum[0],
                                                   fiat='RUB',
                                                   currency_type='fiat',
                                                   expires_in = 1800) # срок годности 30 минут

        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()
        cursor.execute(
            f"INSERT INTO replenishment_request (id_payment,way,data_create,sum,url,id_customer) VALUES (?, ?, ?, ?, ?, ?)",
            (str(fiat_invoice.invoice_id), 'cryptoBot', str(formatted_time), selected_sum[0], fiat_invoice.bot_invoice_url, callback.from_user.id))
        connection.commit()  # сохранение
        cursor.execute(f"SELECT id FROM replenishment_request WHERE id_payment = ? AND status = ?",
                       (str(fiat_invoice.invoice_id), 'not_completed'))
        order_id = cursor.fetchone()
        connection.close()

        await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'💳 Для оплаты нажмите кнопку ниже\n\nСчет действителен 30 минут',
                                     reply_markup=await kb.payment_verification('cryptoBot', order_id[0],
                                                        str(fiat_invoice.invoice_id), fiat_invoice.bot_invoice_url))

        await update_request_replenishment(order_id[0])


@router.callback_query(F.data.startswith('check_payment|'))
async def replenishment(callback: CallbackQuery):
    id_order = callback.data.split('|')[1]
    id_payment = callback.data.split('|')[2]
    method = callback.data.split('|')[3]

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT status FROM replenishment_request WHERE id = ? AND id_payment = ?",
                   (int(id_order), id_payment))
    order_status = cursor.fetchone()
    connection.close()

    if method == 'crystalPAY':
        info = crystalpayAPI.Invoice.getinfo(id_payment)
    elif method == 'cryptoBot':
        invoice = await crypto.get_invoices(invoice_ids= int(id_payment))
        info = {'state': invoice.status}
    else:
        info = {'state': 'rejected'}

    if order_status[0] == 'not_completed': # если заявка не завершена
        if info['state'] == 'payed' or info['state'] == 'paid': # если оплачен  (второе значение для кб)
            current_datetime = dt.now()
            formatted_time = current_datetime.strftime("%H:%M:%S %d-%m-%Y")

            connection = sqlite3.connect('../working_file/data_base.sqlite3')
            cursor = connection.cursor()
            cursor.execute(f"SELECT balance FROM users WHERE id = ?",(callback.from_user.id,))
            balance = cursor.fetchone()
            new_balance = balance[0] + int(info['amount'])
            cursor.execute(f"UPDATE replenishment_request SET status = ?, data_completion = ? WHERE id = ? AND id_payment = ?",
                           ('completed',formatted_time, id_order, id_payment))
            cursor.execute(f"UPDATE users SET balance = ? WHERE id = ?", (new_balance,callback.from_user.id))
            connection.commit()
            connection.close()

            await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                         text=f'✅ Оплата прошла успешно!\n\nНа счёт зачислено: {info['amount']}RUB\n'
                                              f'Текущий баланс: {new_balance}RUB',
                                         reply_markup= kb.back_in_profile)
        else:
            await callback.answer('Платёж не оплачен!', show_alert= True)
    elif order_status[0] == 'completed': # выполнена заявка
        await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'✅ Счёт уже оплачен!\n\nНа него было зачислено: {info['amount']}RUB',
                                     reply_markup=kb.back_in_profile)
    elif order_status[0] == 'rejected': # отклонена заявка
        await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'❌ <b>Оплата не прошла!</b>\n\nЗа отведённое время не была произведена оплата',
                                     reply_markup=kb.back_in_profile)


@router.callback_query(F.data.startswith('withdrawal_'))
async def withdrawal(callback: CallbackQuery, state: FSMContext):
    way = callback.data.split('_')[1]

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT selected_sum FROM create_withdrawal WHERE id = ?", (callback.from_user.id,))
    selected_sum = cursor.fetchone()
    connection.close()

    if selected_sum[0] < 500:
        await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'⚠️ Минимальная сумма вывода 500руб!',
                                     reply_markup=kb.back_in_profile)
        return

    if way == 'SBP':
        await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'Выберите банк 👇',reply_markup=kb.bank)
    elif way == 'bankMap':
        message_id = await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'Введите номер карты для пополнения\n\n'
                                          f'Пример: \n<code>2200 1523 8750 6719</code>',
                                     reply_markup=kb.back_in_profile)
        await state.update_data(bot_message_id= message_id)  # Запоминаем message_id бота
        await state.set_state(Form.number_card)

@router.callback_query(F.data.startswith('bank_'))
async def selected_bank(callback: CallbackQuery, state: FSMContext):
    bank = callback.data.split('_')[1]

    bank_for_db = ''
    if bank == 'sber':
        bank_for_db = 'Сбербанк'
    elif bank == 'alpha':
        bank_for_db = 'Альфа'
    elif bank == 'Tbank':
        bank_for_db = 'Т банк'
    elif bank == 'vtb':
        bank_for_db = 'ВТБ'
    elif bank == 'ozon':
        bank_for_db = 'Озон'
    elif bank == 'another': # когда выбрали другой банк
        message_id = await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                                  text=f'Введите Банк',reply_markup=kb.back_in_profile)
        await state.update_data(bot_message_id=message_id)  # Запоминаем message_id бота
        await state.set_state(Form.another_bank)
        return

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"UPDATE create_withdrawal SET bank = ? WHERE id = ?",(bank_for_db, callback.from_user.id))
    connection.commit()
    connection.close()

    message_id = await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                              text=f'Введите номер телефона для пополнения\n\n'
                                                   f'Пример: \n<code>+7 952 543-72-19</code>',
                                              reply_markup=kb.back_in_profile)
    await state.update_data(bot_message_id=message_id)  # Запоминаем message_id бота
    await state.set_state(Form.number_phone)

@router.message(Form.another_bank)
async def another_bank(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"]  # сообщение для удаления (это которое отослал бот)
    await state.clear()

    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"UPDATE create_withdrawal SET bank = ? WHERE id = ?",
                   (message.text, message.from_user.id))
    connection.commit()
    connection.close()

    message_id = await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,
                                              text=f'Введите номер телефона для пополнения\n\n'
                                                   f'Пример: \n<code>+7 952 543-72-19</code>',
                                              reply_markup=kb.back_in_profile)
    await state.update_data(bot_message_id=message_id)  # Запоминаем message_id бота
    await state.set_state(Form.number_phone)

@router.message(Form.number_phone)
async def number_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"]  # сообщение для удаления (это которое отослал бот)
    await state.clear()

    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"UPDATE create_withdrawal SET phone_or_number_card = ? WHERE id = ?",
                   (message.text, message.from_user.id))
    connection.commit()

    cursor.execute(f"SELECT bank, selected_sum FROM create_withdrawal WHERE id = ?",
                   (message.from_user.id,))
    info_order = cursor.fetchone()
    connection.close()

    sum_with_interest = (info_order[1] * 3) / 100  # сумма которую необходимо вычесть для подсчёта процента
    sum_with_interest = info_order[1] - sum_with_interest  # сумма на вывод с учётом комиссии

    if is_possible_phone_number(message.text): # проверка на существование введённого номера
        await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,
                                     text=f'Проверьте правильность написанных данных:\n\n'
                                          f'💸 Сумма вывода: {info_order[1]}\n'
                                          f'💸 Сумма к получению: {sum_with_interest}\n'
                                          f'🏛️ Банк: {info_order[0]}\n'
                                          f'📱 Номер телефона: {message.text}\n',
                                     reply_markup=kb.create_order_on_withdrawal)
    else:
        message_id = await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,
                                                  text=f'❌ Номер введён некорректно, попробуйте ещё раз\n\n'
                                                       f'Пример: \n<code>+7 952 543-72-19</code>',
                                                  reply_markup=kb.back_in_profile)
        await state.update_data(bot_message_id=message_id)  # Запоминаем message_id бота
        await state.set_state(Form.number_phone)


@router.message(Form.number_card)
async def number_card(message: types.Message, state: FSMContext):
    data = await state.get_data()
    bot_message_id = data["bot_message_id"]  # сообщение для удаления (это которое отослал бот)
    await state.clear()

    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    except TelegramBadRequest:  # если сообщение удалено
        pass

    number_card_str = message.text.replace(" ", "")

    error_message = ''

    try:
        test = int(number_card_str)
        if len(number_card_str) != 16:
            error_message = '❌ Данные для карты введены не корректно\nПопробуйте ещё раз\n\nПример: \n<code>+7 952 543-72-19</code>'
    except ValueError:
        error_message = '❌ Данные для карты введены не корректно\nПопробуйте ещё раз\n\nПример: \n<code>+7 952 543-72-19</code>'

    if error_message:
        message_id = await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,
                                     text=error_message,reply_markup=kb.back_in_profile)
        await state.update_data(bot_message_id=message_id)
        await state.set_state(Form.number_card)
        return

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"UPDATE create_withdrawal SET phone_or_number_card = ?, bank = ? WHERE id = ?",
                   (message.text, None, message.from_user.id))
    connection.commit()

    cursor.execute(f"SELECT selected_sum FROM create_withdrawal WHERE id = ?",(message.from_user.id,))
    selected_sum = cursor.fetchone()
    connection.close()

    sum_with_interest = (selected_sum[0] * 3) / 100  # сумма которую необходимо вычесть для подсчёта процента
    sum_with_interest = selected_sum[0] - sum_with_interest  # сумма на вывод с учётом комиссии

    await edit_or_answer_message(chat_id=message.from_user.id, message_id=bot_message_id,
                                 text=f'Проверьте правильность написанных данных:\n\n'
                                      f'💸 Сумма вывода: {selected_sum[0]}\n'
                                      f'💸 Сумма к получению: {sum_with_interest}\n'
                                      f'💳 Номер карты: {message.text}\n',
                                 reply_markup=kb.create_order_on_withdrawal)

@router.callback_query(F.data == 'confirm_order')
async def confirm_order(callback: CallbackQuery):
    current_datetime = dt.now()
    formatted_time = current_datetime.strftime("%H:%M:%S %d-%m-%Y")

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT balance, withdrawal_balance FROM users WHERE id = ?",(callback.from_user.id,))
    balances = cursor.fetchone()

    cursor.execute(f"SELECT phone_or_number_card, bank, selected_sum FROM create_withdrawal WHERE id = ?",
        (callback.from_user.id,))
    info_order = cursor.fetchone()

    message_error = ''
    if balances[0] < info_order[2]:
        message_error = '⚠️ Внимание!\n\nВаш баланс меньше желаемого вывода!'
    elif info_order[2] < 500:
        message_error = '⚠️ Внимание!\n\nМинимальная сумма вывода 500руб!'
    elif (balances[0] - balances[1]) < info_order[2]:
        message_error = ('⚠️ Внимание!\n\nУ вас достаточно денег на счету, но уже есть заявка на вывод и'
                         ' указанная сумма превышает оставшийся баланс!\n\nДождитесь выполнения заявки')

    sum_with_interest = (info_order[2] * 3) / 100 # сумма которую необходимо вычесть для подсчёта процента
    sum_with_interest = info_order[2] - sum_with_interest # сумма на вывод с учётом комиссии

    new_withdrawal_requests = balances[1] + info_order[2]

    if message_error:
        connection.close()
        await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=message_error,reply_markup=kb.back_in_profile)
        return

    cursor.execute(f"INSERT INTO withdrawal_requests (way,sum,data_create, bank, phone_or_number_card, id_customer)"
                   f" VALUES (?,?,?,?,?,?)", ('admin',info_order[2], formatted_time, info_order[1], info_order[0],
                                                         callback.from_user.id))
    cursor.execute(f"UPDATE users SET withdrawal_balance = ? WHERE id = ?",(new_withdrawal_requests, callback.from_user.id))
    connection.commit()

    cursor.execute(f"SELECT id FROM withdrawal_requests WHERE id_customer = ? AND data_create = ?",
        (callback.from_user.id,formatted_time))
    id_order = cursor.fetchone()

    connection.close()



    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text=f'✅ Заявка успешно направленна менеджерам\n\n'
                                      f'Время выполнения от 5 минут до 24 часов\n'
                                      f'Вам придёт сообщение об успешном выводе',
                                 reply_markup=kb.back_in_profile)

    try: # вывод в сообщения в чат с админами
        await bot.send_message(chat_id=ADMIN_CHAT_ID,
                               text=f'ID заявки:  /order_id_{id_order[0]}_\n\n'
                                    f'ID пользователя:  /user_id_{callback.from_user.id}_\n'
                                    f'user_name пользователя: @{callback.from_user.username}\n\n'
                                    f'💸 Сумма: <code>{sum_with_interest}</code>\n'
                                    f'💳 Реквизиты: <code>{info_order[0]}</code>\n'
                                    f'🏛️ Банк: {info_order[1]}\n', parse_mode= 'HTML')
    except TelegramForbiddenError:
        pass
