# это главный файл в которой мы будем вызывать другие файлы
import asyncio
from aiogram import Bot, Dispatcher

from config import TOKEN # из файла config берём переменную TOKEN в ней записан токен нашего бота
from app.handlers_start import router # из handlers который находится в папке app мы импортируем router
from app.handlers_admin_panel import router as admin_router  # импорт обработчиков админки
from app.handlers_profile import router as profile_router  # импорт обработчиков профиля
from app.handlers_info_and_settings import router as info_and_settings_router  # импорт обработчиков профиля
from app.handlers_shop_and_bonus import router as shop_and_bonus_router  # импорт обработчиков профиля
from app.backup import on_startup
bot = Bot(token = TOKEN) # задаём значение токена в боте (этот токен получаем у fatherBot)
dp = Dispatcher() # это диспетчер работа происходит через него

async def main():
    await on_startup()
    dp.include_router(router) # теперь диспетчер выполняет работу router
    dp.include_router(admin_router)  # подключаем админские обработчики
    dp.include_router(profile_router)  # подключаем обработчики профиля
    dp.include_router(info_and_settings_router)  # подключаем обработчики информации и настроек
    dp.include_router(shop_and_bonus_router)  # подключаем обработчики магазина и раздела бонусы
    await dp.start_polling(bot) # если ответ есть от телеграмма, то бот будет работать

if __name__ == '__main__':
    try:
        print("Бот начал работу")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот завершил работу")
