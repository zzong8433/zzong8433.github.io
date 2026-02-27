"""
Scheduler - 리마인더 & 매일 아침 브리핑 발송
"""
import asyncio
import logging
from datetime import datetime, time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import db
import ai_service

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")

# 봇 인스턴스 - bot.py에서 주입
_bot = None


def set_bot(bot):
    global _bot
    _bot = bot


async def check_reminders():
    """미발송 리마인더를 확인하고 전송"""
    if not _bot:
        return

    reminders = db.get_pending_reminders()
    for rem in reminders:
        try:
            msg = rem["message"]
            if rem.get("task_title"):
                msg = f"📌 {rem['task_title']}\n\n{msg}"

            await _bot.send_message(chat_id=rem["user_id"], text=msg)
            db.mark_reminder_sent(rem["id"])
            logger.info(f"Reminder {rem['id']} sent to user {rem['user_id']}")
        except Exception as e:
            logger.error(f"Failed to send reminder {rem['id']}: {e}")


async def send_morning_briefing():
    """매일 아침 9시에 오늘의 업무 브리핑 전송"""
    if not _bot:
        return

    with db.get_conn() as conn:
        users = conn.execute("SELECT user_id FROM users").fetchall()

    for user_row in users:
        user_id = user_row["user_id"]
        try:
            tasks = db.get_today_tasks(user_id)
            stats = db.get_stats(user_id)

            if stats["pending"] == 0 and stats["in_progress"] == 0:
                continue

            message = ai_service.generate_daily_message(tasks, stats)
            await _bot.send_message(chat_id=user_id, text=message)
            logger.info(f"Morning briefing sent to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send morning briefing to {user_id}: {e}")


async def send_deadline_warnings():
    """마감이 가까운 태스크에 대해 부드러운 알림 전송"""
    if not _bot:
        return

    with db.get_conn() as conn:
        users = conn.execute("SELECT user_id FROM users").fetchall()

    for user_row in users:
        user_id = user_row["user_id"]
        try:
            urgent_tasks = db.get_tasks_due_soon(user_id, hours=6)
            for task in urgent_tasks:
                nudge = ai_service.generate_nudge_message(task)
                await _bot.send_message(chat_id=user_id, text=f"⏰ {nudge}")
        except Exception as e:
            logger.error(f"Failed to send deadline warning to {user_id}: {e}")


def start_scheduler():
    """스케줄러 시작"""
    # 1분마다 리마인더 체크
    scheduler.add_job(
        check_reminders,
        IntervalTrigger(minutes=1),
        id="check_reminders",
        replace_existing=True,
    )

    # 매일 아침 9시 브리핑
    scheduler.add_job(
        send_morning_briefing,
        CronTrigger(hour=9, minute=0),
        id="morning_briefing",
        replace_existing=True,
    )

    # 매일 오후 2시, 5시에 마감 임박 알림
    scheduler.add_job(
        send_deadline_warnings,
        CronTrigger(hour=14, minute=0),
        id="deadline_warnings_afternoon",
        replace_existing=True,
    )
    scheduler.add_job(
        send_deadline_warnings,
        CronTrigger(hour=17, minute=0),
        id="deadline_warnings_evening",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    scheduler.shutdown()
    logger.info("Scheduler stopped")
