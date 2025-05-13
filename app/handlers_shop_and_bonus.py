import sqlite3

from app.general_def import edit_or_answer_message, send_new_message

from datetime import datetime as dt
from aiogram import F,Bot, Router, types
from aiogram.types import CallbackQuery

import app.keyboards as kb # импортируем клавиатуру и сокращаем её на 'kb'

from config import TOKEN, CRYSTAL_API_LOGIN, CRYSTAL_API_SECRETKEY1, CRYSTAL_API_SECRETKEY2, CRYPTO_TOKEN

from crystalpay_sdk import CrystalPAY # касса
crystalpayAPI = CrystalPAY(CRYSTAL_API_LOGIN, CRYSTAL_API_SECRETKEY1, CRYSTAL_API_SECRETKEY2)

from aiocryptopay import AioCryptoPay, Networks # КБ
crypto = AioCryptoPay(token=CRYPTO_TOKEN, network=Networks.TEST_NET) # КБ

router = Router() # это почти как диспетчер только для handlers

bot = Bot(token = TOKEN)


@router.callback_query(F.data == 'shop')
async def select_currency(callback: CallbackQuery):
    await edit_or_answer_message(chat_id=callback.from_user.id, message_id= callback.message.message_id,
                                text = f'Выберите действие 👇',reply_markup = kb.shop)


@router.callback_query(F.data == 'show_all_levels')
async def select_currency(callback: CallbackQuery):
    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text=f'Выберите действие желаемый уровень 👇', reply_markup=await kb.show_all_levels())


@router.callback_query(F.data.startswith('show_buy_level_'))
async def show_buy_level(callback: CallbackQuery):
    level = int(callback.data.split('_')[3])

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT emoji_level, prise, percent_one_level, percent_two_level, percent_three_level FROM levels WHERE level = ?",
                   (level,))
    level_info = cursor.fetchone()  # Извлекает первую найденную строку
    connection.close()

    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text=f'Уровень:  {level_info[0]} {level}\n'
                                      f'Цена: {level_info[1]}\n'
                                      f'Прибыль с реферала первый ступени: {level_info[2]}%\n'
                                      f'Прибыль с реферала второй ступени: {level_info[3]}%\n'
                                      f'Прибыль с реферала третьей ступени: {level_info[4]}%',
                                 reply_markup=await kb.buy_level(level, level_info[1]))


@router.callback_query(F.data.startswith('buy_level_'))
async def buy_level(callback: CallbackQuery):
    level = int(callback.data.split('_')[2])
    prise = int(callback.data.split('_')[3])

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT balance, withdrawal_balance, level  FROM users WHERE id = ?", (callback.from_user.id,))
    info_user = cursor.fetchone()  # Извлекает первую найденную строку
    connection.close()

    if info_user[2] != 0:
        await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'⚠️ Внимание! \nУ вас уже есть {info_user[2]} уровень' ,
                                     reply_markup=kb.back_in_all_levels)
        return

    if info_user[0] - info_user[1] < prise: # если имеющийся баланс меньше цены

        if info_user[1] == 0: # если у пользователя нет денег на выводе
            message_with_balance = f'Ваш текущий баланс: {info_user[0]}'
        else:
            message_with_balance = (f'Ваш текущий баланс: {info_user[0]}\n'
                                    f'Но у вас есть {info_user[1]} ₽ на выводе\n'
                                    f'Следовательно ваши имеющиеся средства {info_user[0] - info_user[1]}')

        await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'❌ Недостаточно средств!\n\n'
                                          f'{message_with_balance}',
                                     reply_markup=kb.replenishment_or_back_main_menu)

    else:
        current_datetime = dt.now()
        formatted_time = current_datetime.strftime("%H:%M:%S %d-%m-%Y")

        new_balance = info_user[0] - prise # формируем новый баланс

        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()
        cursor.execute(f"UPDATE users SET balance = ?, level = ? WHERE id = ?",
                       (new_balance, level, callback.from_user.id))
        cursor.execute(f"INSERT INTO purchase_of_services (id_buyer, services, level, prise, date) VALUES (?, ?, ?, ?, ?)",
            (callback.from_user.id, 'buy_level', level, prise, formatted_time))
        connection.commit()

        cursor.execute(f"SELECT owner_id FROM users WHERE id = ?", (callback.from_user.id,))
        id_owner_this_referral = cursor.fetchone()

        if id_owner_this_referral[0]:  # работа для кого он является рефераллом первой ступени
            cursor.execute(f"SELECT owner_id, balance, level, total_earned, id, notifications_from_one_stage_referral  "
                           f"FROM users WHERE id = ?",
                           (id_owner_this_referral[0],))
            owner_one_stage = cursor.fetchone()
            if owner_one_stage[2] != 0:
                cursor.execute(f"SELECT percent_one_level FROM levels WHERE level = ?",(owner_one_stage[2],))
                info_level = cursor.fetchone()

                sum_accruals = (prise * info_level[0]) / 100 # сумма начисления для владельца этого реферала

                cursor.execute(f"INSERT INTO profit_from_referrals (id_recipient, id_referral, sum, step_referral, return_percentage, date)"
                               f" VALUES (?, ?, ?, ?, ?, ?)",
                    (owner_one_stage[4], callback.from_user.id, sum_accruals, 1, info_level[0], formatted_time))

                new_balance = owner_one_stage[1] + sum_accruals

                new_total_earned = owner_one_stage[3] + sum_accruals

                cursor.execute(f"UPDATE users SET balance = ?, total_earned = ? WHERE id = ?",
                               (new_balance, new_total_earned, owner_one_stage[4]))

                if owner_one_stage[5] == 1: # если необходимо отослать сообщение (это меняется в настройках)
                    await send_new_message(owner_one_stage[4], f'💸 Реферал первой ступен совершил покупку \n\nВам начислено '
                                                                         f'{sum_accruals} ₽\nВаш текущий баланс = {new_balance} ₽')
            else:
                await send_new_message(owner_one_stage[4], f'💸 Один из ваших рефералов первой ступени совершил покупку, \n'
                                                                 f'приобретя уровень вы могли бы получить с этой покупки процент',
                                       reply_markup = kb.only_shop)

            if owner_one_stage[0]:# если у реферала первой ступени есть владелиц (это будет 2 ступень)
                cursor.execute(f"SELECT owner_id, balance, level, total_earned, id, notifications_from_two_stage_referral"
                               f" FROM users WHERE id = ?",
                               (owner_one_stage[0],))
                owner_two_stage = cursor.fetchone()

                if owner_two_stage[2] != 0:
                    cursor.execute(f"SELECT percent_two_level FROM levels WHERE level = ?", (owner_two_stage[2],))
                    info_level = cursor.fetchone()

                    sum_accruals = (prise * info_level[0]) / 100  # сумма начисления для владельца этого реферала

                    cursor.execute(
                        f"INSERT INTO profit_from_referrals (id_recipient, id_referral, sum, step_referral, return_percentage, date)"
                        f" VALUES (?, ?, ?, ?, ?, ?)",
                        (owner_two_stage[4], callback.from_user.id, sum_accruals, 2, info_level[0], formatted_time))

                    new_balance = owner_two_stage[1] + sum_accruals

                    new_total_earned = owner_two_stage[3] + sum_accruals

                    cursor.execute(f"UPDATE users SET balance = ?, total_earned = ? WHERE id = ?",
                                   (new_balance, new_total_earned, owner_two_stage[4]))

                    if owner_two_stage[5] == 1: # если необходимо отослать сообщение (это меняется в настройках)
                        await send_new_message(owner_two_stage[4],
                                               f'💸 Реферал второй ступен совершил покупку \n\nВам начислено '
                                               f'{sum_accruals} ₽\nВаш текущий баланс = {new_balance} ₽')
                else:
                    await send_new_message(owner_two_stage[4],
                                           f'💸 Один из ваших рефералов второй ступени совершил покупку, \n'
                                           f'приобретя уровень вы могли бы получить с этой покупки процент',
                                           reply_markup=kb.only_shop)
                if owner_two_stage[0]: # если у реферала второй ступени есть владелиц (это будет 3 ступень)
                    cursor.execute(f"SELECT owner_id, balance, level, total_earned, id, notifications_from_three_stage_referral"
                                   f" FROM users WHERE id = ?",
                                   (owner_two_stage[0],))
                    owner_three_stage = cursor.fetchone()

                    if owner_three_stage[2] != 0:
                        cursor.execute(f"SELECT percent_three_level FROM levels WHERE level = ?",
                                       (owner_three_stage[2],))
                        info_level = cursor.fetchone()

                        sum_accruals = (prise * info_level[0]) / 100  # сумма начисления для владельца этого реферала

                        cursor.execute(
                            f"INSERT INTO profit_from_referrals (id_recipient, id_referral, sum, step_referral, return_percentage, date)"
                            f" VALUES (?, ?, ?, ?, ?, ?)",
                            (owner_three_stage[4], callback.from_user.id, sum_accruals, 3, info_level[0], formatted_time))

                        new_balance = owner_three_stage[1] + sum_accruals

                        new_total_earned = owner_three_stage[3] + sum_accruals

                        cursor.execute(f"UPDATE users SET balance = ?, total_earned = ? WHERE id = ?",
                                       (new_balance, new_total_earned, owner_three_stage[4]))

                        if owner_three_stage[5] == 1: # если необходимо отослать сообщение о пополнении
                            await send_new_message(owner_three_stage[4],
                                                   f'💸 Реферал третьей ступен совершил покупку \n\nВам начислено '
                                                   f'{sum_accruals} ₽\nВаш текущий баланс = {new_balance} ₽')
                    else:
                        await send_new_message(owner_three_stage[4],
                                               f'💸 Один из ваших рефералов третьей ступени совершил покупку, \n'
                                               f'приобретя уровень вы могли бы получить с этой покупки процент',
                                               reply_markup=kb.only_shop)

        connection.commit()  # сохранение
        connection.close()



        await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'💸 Уровень {level} успешно приобретён!',
                                     reply_markup=kb.back_in_main_menu)



@router.callback_query(F.data == 'improve')
async def improve(callback: CallbackQuery):
    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT level  FROM users WHERE id = ?", (callback.from_user.id,))
    level = cursor.fetchone()  # Извлекает первую найденную строку
    connection.close()

    if level[0] == 0:
        await callback.answer('Для открытия этого раздела необходимо приобрести уровень!', show_alert = True)
        return

    if level[0] == 3:
        await callback.answer('У вас уже максимальный уровень!', show_alert= True)
        return

    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                 text=f'Выберите желаемый уровень для улучшения 👇',
                                 reply_markup=await kb.show_level_for_improve(level[0]))


@router.callback_query(F.data.startswith('show_level_for_improve|'))
async def show_level_for_improve(callback: CallbackQuery):
    level = int(callback.data.split('|')[1]) # желаемый уровень
    prise = int(callback.data.split('|')[2]) # его цена с учётом штрафа за улучшение

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT percent_one_level, percent_two_level, percent_three_level, emoji_level  FROM levels WHERE level = ?",
                   (level,))
    level_info = cursor.fetchone()  # Извлекает первую найденную строку
    connection.close()

    await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'Уровень:  {level_info[3]} {level}\n\n'
                                      f'Цена улучшения: {prise}\n'
                                      f'Прибыль с реферала первый ступени: {level_info[0]}%\n'
                                      f'Прибыль с реферала второй ступени: {level_info[1]}%\n'
                                      f'Прибыль с реферала третьей ступени: {level_info[2]}%',
                                     reply_markup= await kb.buy_improve(level, prise) )

@router.callback_query(F.data.startswith('buy_improve_'))
async def buy_improve(callback: CallbackQuery):
    level = int(callback.data.split('_')[2])  # желаемый уровень
    prise = int(callback.data.split('_')[3])  # его цена с учётом штрафа за улучшение

    connection = sqlite3.connect('../working_file/data_base.sqlite3')
    cursor = connection.cursor()
    cursor.execute(f"SELECT balance, withdrawal_balance, level FROM users WHERE id = ?",(callback.from_user.id,))
    info_user = cursor.fetchone()  # Извлекает первую найденную строку
    connection.close()

    if info_user[2] >= level: # если уровень пользователя больше или равен уровня для улучшения
        await callback.answer(text=f'⚠️ Внимание! \n\nВаш уровень выше желаемого для улучшения\nУлучшите на другой уровень!',
                            show_alert = True)
        return

    if info_user[0] - info_user[1] < prise: # если имеющийся баланс меньше цены

        if info_user[1] == 0: # если у пользователя нет денег на выводе
            message_with_balance = f'Ваш текущий баланс: {info_user[0]}'
        else:
            message_with_balance = (f'Ваш текущий баланс: {info_user[0]}\n'
                                    f'Но у вас есть {info_user[1]} ₽ на выводе\n'
                                    f'Следовательно ваши имеющиеся средства {info_user[0] - info_user[1]}')

        await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'❌ Недостаточно средств!\n\n'
                                          f'{message_with_balance}',
                                     reply_markup=kb.replenishment_or_back_main_menu)
    else:
        current_datetime = dt.now()
        formatted_time = current_datetime.strftime("%H:%M:%S %d-%m-%Y")

        new_balance = info_user[0] - prise  # формируем новый баланс

        connection = sqlite3.connect('../working_file/data_base.sqlite3')
        cursor = connection.cursor()
        cursor.execute(f"UPDATE users SET balance = ?, level = ? WHERE id = ?",
                       (new_balance, level, callback.from_user.id))
        cursor.execute(f"INSERT INTO purchase_of_services (id_buyer, services, level, prise, date) VALUES (?, ?, ?, ?, ?)",
            (callback.from_user.id, 'upgrade_level', level, prise, formatted_time))
        connection.commit()
        connection.close()

        await edit_or_answer_message(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                     text=f'🚀 Уровень успешно улучшен до {level}!',
                                     reply_markup=kb.back_in_main_menu)






