from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.config import CHANNEL_URL, MANAGER_URL
from aiogram.utils.keyboard import InlineKeyboardBuilder
import sqlite3
# это для нескольких кнопок в сообщение от бота

async def main_menu(user_id: int):
    keyboard = InlineKeyboardBuilder()

    keyboard.add(InlineKeyboardButton(text='Профиль', callback_data='profile'))

    keyboard.row(
        InlineKeyboardButton(text='Магазин', callback_data='shop'),
        InlineKeyboardButton(text='Бонусы', callback_data='bonus')
    )

    keyboard.row(
    InlineKeyboardButton(text='Инфо', callback_data='info'),
        InlineKeyboardButton(text='Настройки', callback_data='settings')
    )
    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT admin_id FROM admins WHERE admin_id = ?", (user_id,))
    check_for_admin = cursor.fetchone()  # Извлекает первую найденную строку
    connection.close()

    keyboard.adjust(1, 2, 2) # каждое значение это сколько кнопок находятся на одной строке

    if check_for_admin:
        keyboard.add(InlineKeyboardButton(text='Панель админа', callback_data='admin_panel'))
        keyboard.adjust(1, 2, 2, 1)

    return keyboard.as_markup()

shop = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Приобрести', callback_data='show_all_levels')],
    [InlineKeyboardButton(text='Улучшить', callback_data='improve')],
    [InlineKeyboardButton(text='Назад', callback_data='main_menu')],
])

replenishment_or_back_main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Пополнить баланс', callback_data='money_replenishment')],
    [InlineKeyboardButton(text='Назад', callback_data='main_menu')],
])

async def show_all_levels():
    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT level, prise, emoji_level FROM levels WHERE level != ? AND level != ?", (0,9))
    all_level = cursor.fetchall()  # Извлекает первую найденную строку
    connection.close()

    sorted_level = sorted(all_level, key=lambda x: x[0], reverse = True)  # сортируем массив по первому элементу вложенного массива

    keyboard = InlineKeyboardBuilder()
    for level in sorted_level:
        keyboard.add(InlineKeyboardButton(text=f'{level[2]} {level[0]}   {level[1]} ₽', callback_data=f'show_buy_level_{level[0]}'))

    keyboard.add(InlineKeyboardButton(text=f'Назад', callback_data=f'shop'))

    keyboard.adjust(1)
    return keyboard.as_markup()

async def buy_level(level: int, prise: int):
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text=f'Приобрести', callback_data=f'buy_level_{level}_{prise}'))
    keyboard.add(InlineKeyboardButton(text=f'Назад', callback_data=f'show_all_levels'))
    keyboard.adjust(1)
    return keyboard.as_markup()

async def show_level_for_improve(current_level: int):
    """Формула по которой вычисляем стоимость вычисления\n
     стоимость_желаемого_уровня - стоимость_текущего_уровня + 50 ₽ штраф\n
     пример 500 - 250 + 50 = 300 это стоимость перехода с 1 уровня на 2"""
    keyboard = InlineKeyboardBuilder()

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()

    cursor.execute(f"SELECT level, prise, emoji_level FROM levels WHERE level != ?", (0,))
    all_levels = cursor.fetchall()  # Извлекает первую найденную строку
    cursor.execute(f"SELECT prise FROM levels WHERE level = ?", (current_level,))
    prise_current_level = cursor.fetchone()  # Извлекает первую найденную строку

    connection.close()

    sorted_levels = sorted(all_levels, key=lambda x: x[0])  # сортируем массив по первому элементу вложенного массива

    for level in sorted_levels:
        if level[0] == 9: # это уровень партнёра его не надо показывать
            continue

        if level[0] > current_level: # если уровень выше уровня пользователя
            prise_level = level[1] - prise_current_level[0] + 50 # это формула по которой вычисляем стоимость улучшения
            keyboard.add(InlineKeyboardButton(text=f'Уровень {level[2]} {level[0]} за {prise_level} ₽',
                                              callback_data=f'show_level_for_improve|{level[0]}|{prise_level}'))

    keyboard.add(InlineKeyboardButton(text=f'Назад', callback_data=f'shop'))

    keyboard.adjust(1)
    return keyboard.as_markup()

async def buy_improve(selected_level: int, prise: int):
    keyboard = InlineKeyboardBuilder()

    keyboard.add(InlineKeyboardButton(text=f'Улучшить', callback_data=f'buy_improve_{selected_level}_{prise}'))
    keyboard.add(InlineKeyboardButton(text=f'Назад', callback_data=f'improve'))

    keyboard.adjust(1)
    return keyboard.as_markup()

async def settings(user_id: int):
    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT selected_currency FROM users WHERE id = ?", (user_id,))
    selected_currency = cursor.fetchone()  # Извлекает первую найденную строку
    connection.close()

    if selected_currency[0] == 'RUB':
        flag = '🇷🇺'
        opposite_flag = 'USD' #  это та валюта которую мы установим, при нажатии кнопки (необходимо поменять на противоположную)
    else:
        flag = '🇬🇧'
        opposite_flag = 'RUB'

    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text=f'{flag} Основная валюта', callback_data= f'change_currency_{opposite_flag}'))
    keyboard.add(InlineKeyboardButton(text=f'Уведомления об оплате', callback_data= f'notification_replenishment'))
    keyboard.add(InlineKeyboardButton(text=f'Назад', callback_data= f'main_menu'))
    keyboard.adjust(1)

    return keyboard.as_markup()

async def notification_replenishment(user_id: int):
    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT notifications_from_one_stage_referral, notifications_from_two_stage_referral,"
                   f"notifications_from_three_stage_referral  FROM users WHERE id = ?", (user_id,))
    notification = cursor.fetchone()  # Извлекает первую найденную строку
    connection.close()

    opposite_one_stage = 1
    opposite_two_stage = 1
    opposite_three_stage = 1

    info_about_the_one_stage = 'выкл.'
    info_about_the_two_stage = 'выкл.'
    info_about_the_three_stage = 'выкл.'

    if notification[0] == 1:
        opposite_one_stage = 0
        info_about_the_one_stage = 'вкл.'

    if notification[1] == 1:
        opposite_two_stage = 0
        info_about_the_two_stage = 'вкл.'

    if notification[2] == 1:
        opposite_three_stage = 0
        info_about_the_three_stage = 'вкл.'

    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text=f'1 ступень {info_about_the_one_stage}',
                                      callback_data=f'change_notification_stage|1|{opposite_one_stage}'))
    keyboard.add(InlineKeyboardButton(text=f'2 ступень {info_about_the_two_stage}',
                                      callback_data=f'change_notification_stage|2|{opposite_two_stage}'))
    keyboard.add(InlineKeyboardButton(text=f'3 ступень {info_about_the_three_stage}',
                                      callback_data=f'change_notification_stage|3|{opposite_three_stage}'))
    keyboard.add(InlineKeyboardButton(text=f'Назад', callback_data=f'settings'))
    keyboard.adjust(1)

    return keyboard.as_markup()


profile_keb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='💸 Пополнить баланс', callback_data='money_replenishment')],
    [InlineKeyboardButton(text='💰 Вывод средств', callback_data='money_withdrawal')],
    [InlineKeyboardButton(text='📂 История транзакций', callback_data='history_transactions')],
    [InlineKeyboardButton(text='Назад', callback_data='main_menu')],
])

async def replenishment():
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text='Банковская карта', callback_data=f'replenishment_bankMap'))
    keyboard.add(InlineKeyboardButton(text='Криптовалюта', callback_data=f'replenishment_crystalPAY'))
    keyboard.add(InlineKeyboardButton(text='CryptoBot', callback_data=f'replenishment_cryptoBot'))
    keyboard.add(InlineKeyboardButton(text='Назад', callback_data=f'profile'))

    keyboard.adjust(1, 1, 1, 1)

    return keyboard.as_markup()

async def withdrawal():
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text='СБП', callback_data=f'withdrawal_SBP'))
    keyboard.add(InlineKeyboardButton(text='Карта банка', callback_data=f'withdrawal_bankMap'))
    keyboard.add(InlineKeyboardButton(text='Назад', callback_data=f'profile'))

    keyboard.adjust(1, 1, 1)

    return keyboard.as_markup()

transaction_history = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='История прибыли', callback_data='history_profit')],
    [InlineKeyboardButton(text='История пополнений', callback_data='history_replenishment')],
    [InlineKeyboardButton(text='История выводов', callback_data='history_withdrawal')],
    [InlineKeyboardButton(text='Назад', callback_data='profile')],
])

async def history_replenishment(user_id: int, selected_history: str):
    '''selected_history == replenishment_request or withdrawal_requests or profit_from_referrals\n
       selected_history это название таблицы в БД по которой необходимо показать историю транзакций'''
    keyboard = InlineKeyboardBuilder()
    counter = 0

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()

    orders = []
    if selected_history == 'replenishment_request' or selected_history == 'withdrawal_requests':
        cursor.execute(f"SELECT id, status, sum FROM {selected_history} WHERE id_customer = ?", (user_id,))
        all_orders = cursor.fetchall()  # Извлекает все найденную строку

        if all_orders:
            for order in all_orders:
                status = ''
                if order[1] == 'not_completed':
                    status = 'не оплачен'
                    if selected_history == 'withdrawal_requests': # это для вывода
                        status = 'в обработке'
                elif order[1] == 'completed':
                    status = 'выполнен'
                elif order[1] == 'rejected':
                    status = 'отклонён'

                orders.append([order[0],order[2], status])

    elif selected_history == 'profit_from_referrals':
        cursor.execute(f"SELECT id, sum FROM {selected_history} WHERE id_recipient = ?", (user_id,))
        all_orders = cursor.fetchall()  # Извлекает все найденную строку

        if all_orders:
            for order in all_orders:
                orders.append([order[0], str(order[1]), ' '])

    connection.close()
    sorted_orders = sorted(orders, key=lambda x: x[0]) # сортируем массив по первому элементу вложенного массива

    for order in sorted_orders:
        keyboard.add(InlineKeyboardButton(text=f'№{order[0]}   на {order[1]} RUB   {order[2]}',
                                          callback_data=f'show_order_for_user|{selected_history}|{order[0]}'))
        counter += 1
        if counter == 100:
            break


    keyboard.add(InlineKeyboardButton(text=f'Назад', callback_data=f'history_transactions'))
    keyboard.adjust(1)
    return keyboard.as_markup()


bank = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Сбербанк',  callback_data='bank_sber')],
    [InlineKeyboardButton(text='Альфа банк',  callback_data='bank_alpha')],
    [InlineKeyboardButton(text='Т банк',  callback_data='bank_Tbank')],
    [InlineKeyboardButton(text='ВТБ',  callback_data='bank_vtb')],
    [InlineKeyboardButton(text='Озон',  callback_data='bank_ozon')],
    [InlineKeyboardButton(text='Другой банк',  callback_data='bank_another')],
    [InlineKeyboardButton(text='Назад', callback_data='withdrawal_SBP')],
])

create_order_on_withdrawal = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Подтвердить заявку',  callback_data='confirm_order')],
    [InlineKeyboardButton(text='Сформировать заново',  callback_data='money_withdrawal')],
    [InlineKeyboardButton(text='Назад', callback_data='profile')],
])
async def payment_manager(back_button: str = 'profile'):
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text='Ссылка на менеджера', url=MANAGER_URL))
    keyboard.add(InlineKeyboardButton(text='Назад', callback_data= back_button))
    keyboard.adjust(1, 1, 1)
    return keyboard.as_markup()

async def payment_verification(method: str, order_id: int, id_check: str, url_payment: str = None, where_back: str = 'profile'):
    '''where_back это куда отсылать обратно по умолчания в профиль, но можно указать  history_replenishment'''
    keyboard = InlineKeyboardBuilder()

    keyboard.add(InlineKeyboardButton(text='Ссылка на оплату', url=url_payment))
    if method == 'crystalPAY':
        keyboard.add(InlineKeyboardButton(text='Проверить оплату', callback_data=f'check_payment|{order_id}|{id_check}|{method}'))
    elif method == 'cryptoBot':
        keyboard.add(InlineKeyboardButton(text='Проверить оплату',callback_data=f'check_payment|{order_id}|{id_check}|{method}'))
    keyboard.add(InlineKeyboardButton(text='Назад', callback_data= where_back))

    keyboard.adjust(1, 1, 1)

    return keyboard.as_markup()


admin_panel = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Заявки', callback_data='orders')],
    [InlineKeyboardButton(text='Просмотр данных', callback_data='show_data')],
    [InlineKeyboardButton(text='Изменение lvl', callback_data='change_level')],
    [InlineKeyboardButton(text='Рассылка всем', callback_data='mailing_all_info')],
    [InlineKeyboardButton(text='Добавить админа', callback_data='add_admin')],
    [InlineKeyboardButton(text='Удалить админа', callback_data='delete_admin')],
    [InlineKeyboardButton(text='Назад', callback_data='main_menu')],
])

orders = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Создать заявку на пополнение', callback_data='add_orders')],
    [InlineKeyboardButton(text='Заявки на вывод', callback_data='my_orders_withdrawal')],
    [InlineKeyboardButton(text='Назад', callback_data='admin_panel')],
])

async def all_orders():
    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT id FROM withdrawal_requests WHERE status = ?",('not_completed',))
    all_orders = cursor.fetchall()  # Извлекает все найденную строку
    connection.close()

    keyboard = InlineKeyboardBuilder()
    counter = 0
    for id_order in all_orders:
        keyboard.add(InlineKeyboardButton(text=f'{id_order[0]}', callback_data=f'show_order|{id_order[0]}')) # в конец добавляем id заявки

        counter += 1
        if counter == 100:
            break

    keyboard.add(InlineKeyboardButton(text='Назад', callback_data='orders'))

    keyboard.adjust(1)  # 1 кнопка в строке
    return keyboard.as_markup()

async def info_order(id_order: str):
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text='Выполнить', callback_data=f'confirm_output|{id_order}'))
    keyboard.add(InlineKeyboardButton(text='Отклонить', callback_data=f'reject_output|{id_order}'))
    keyboard.add(InlineKeyboardButton(text='Назад', callback_data='orders'))
    keyboard.adjust(1, 1, 1)
    return keyboard.as_markup()

async def variants_levels(user_id: str):
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text='0', callback_data=f'set_level_0_{user_id}'))
    keyboard.add(InlineKeyboardButton(text='1', callback_data=f'set_level_1_{user_id}'))
    keyboard.add(InlineKeyboardButton(text='2', callback_data=f'set_level_2_{user_id}'))
    keyboard.add(InlineKeyboardButton(text='3', callback_data=f'set_level_3_{user_id}'))
    keyboard.add(InlineKeyboardButton(text='Партнёр', callback_data=f'set_level_4_{user_id}'))
    keyboard.add(InlineKeyboardButton(text='Назад', callback_data='admin_panel'))

    keyboard.adjust(1, 1, 1, 1, 1, 1)

    return keyboard.as_markup()

mailing_all_info = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Отослать', callback_data='mailing_confirmation')],
    [InlineKeyboardButton(text='Изменить сообщение', callback_data='change_message')],
    [InlineKeyboardButton(text='Прикрепить фото', callback_data='attach_file')],
    [InlineKeyboardButton(text='Открепить фото', callback_data='unpin_file')],
    [InlineKeyboardButton(text='Назад', callback_data='admin_panel')],
])

choice_for_mailing = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Подтвердить', callback_data='mailing_all')],
    [InlineKeyboardButton(text='Назад', callback_data='mailing_all_info')],
])

back_in_history_profit =  InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Назад', callback_data='history_profit')],
])

back_in_history_replenishment =  InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Назад', callback_data='history_replenishment')],
])

back_in_history_withdrawal =  InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Назад', callback_data='history_withdrawal')],
])

back_in_profile =  InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Назад', callback_data='profile')],
])

back_in_admin_panel =  InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Назад', callback_data='admin_panel')],
])

back_in_orders =  InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Назад', callback_data='orders')],
])

back_in_mailing_all =  InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Назад', callback_data='mailing_all_info')],
])

back_in_main_menu =  InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Назад', callback_data='main_menu')],
])

back_in_all_levels =  InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Назад', callback_data='show_all_levels')],
])

only_shop =  InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Магазин', callback_data='shop')],
])

subscription_verification = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Канал', url = CHANNEL_URL)],
    [InlineKeyboardButton(text='Проверить подписку', callback_data='subscription_verification')],
])

select_currency = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='🇷🇺 RUB', callback_data='selected_currency_RUB')],
    [InlineKeyboardButton(text='🇬🇧 USD', callback_data='selected_currency_USD')],
])

manager_url = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Менеджер', url=MANAGER_URL)],
])

