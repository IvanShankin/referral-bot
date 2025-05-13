import asyncio
import os
import shutil
import datetime as dt
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger # для backup


scheduler = AsyncIOScheduler()

async def scheduled_task(): # это будет выполняться по расписанию
    try:
        os.mkdir(f'working_file/backup/{dt.date.today()}') # создание папки
        shutil.copy2('data_base.sqlite3', f'working_file/backup/{dt.date.today()}') # копирование БД
    except FileExistsError:
        print(f'backup за {dt.date.today()} пропущен т.к. такой файл уже существует')

# Настройка триггера для выполнения задачи в определенные дни недели каждый понедельник в 4:00
scheduler.add_job(scheduled_task, CronTrigger(day_of_week='mon', hour=4, minute=0)) # для backup
async def on_startup():
    scheduler.start()# Запуск планировщика


