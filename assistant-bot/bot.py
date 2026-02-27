"""
ADHD 친화 업무 비서 텔레그램 봇
- 자연어로 업무 등록 → AI가 자동 세분화
- WBS 생성, 데드라인 관리, 부드러운 리마인더
- Google Calendar / Tasks / Sheets 자동 동기화
"""
import logging
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import db
import ai_service
import google_service
import scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")


# ── 헬퍼 함수 ──


def _format_task_list(tasks: list[dict], show_id: bool = True) -> str:
    if not tasks:
        return "등록된 할 일이 없어요! 🎉"

    lines = []
    for t in tasks:
        status_icon = {"pending": "⬜", "in_progress": "🔄", "done": "✅"}.get(t["status"], "⬜")
        priority_icon = {1: "🔴", 2: "🟡", 3: "🟢"}.get(t["priority"], "")

        line = f"{status_icon} "
        if show_id:
            line += f"`#{t['id']}` "
        line += f"{priority_icon} {t['title']}"

        if t.get("deadline"):
            line += f"\n   📅 {t['deadline'][:16]}"
        if t.get("estimated_min"):
            line += f" ⏱️ {t['estimated_min']}분"

        lines.append(line)

    return "\n\n".join(lines)


def _task_context(user_id: int) -> str:
    """AI에게 전달할 현재 태스크 컨텍스트"""
    tasks = db.get_tasks(user_id)
    if not tasks:
        return "현재 등록된 태스크가 없습니다."

    lines = []
    for t in tasks:
        lines.append(f"- [{t['status']}] {t['title']} (마감: {t.get('deadline', '없음')})")
    return "\n".join(lines)


async def _sync_to_google(user_id: int, title: str, deadline: str = None, description: str = None):
    """Google Calendar + Tasks + Sheets에 동기화"""
    if not google_service.is_connected(user_id):
        return

    google_service.add_to_calendar(user_id, title, deadline, description)
    google_service.add_to_google_tasks(user_id, title, deadline, description)
    google_service.log_to_sheet(
        user_id,
        task_title=title,
        description=description or "",
        deadline=deadline or "",
        status="pending",
    )


# ── 커맨드 핸들러 ──


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    welcome = f"""안녕하세요, {user.first_name}님! 👋

저는 당신의 업무 비서예요.
ADHD 특성을 이해하고, 업무를 부담 없이 작게 쪼개서 도와드릴게요.

**사용법은 간단해요:**
• 할 일을 자연어로 말씀해주세요
  예: "다음 주 금요일까지 보고서 작성해야 해"
• 저는 자동으로 작은 단계로 쪼개드려요

**주요 명령어:**
/tasks - 내 할 일 보기
/done `번호` - 완료 처리
/wbs `프로젝트 설명` - WBS 생성
/today - 오늘 할 일
/stats - 내 통계
/google - Google 계정 연결
/help - 도움말

일단 뭐든 편하게 말씀해보세요! 💪"""

    await update.message.reply_text(welcome, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """**📋 명령어 목록**

**할 일 관리**
• 그냥 자연어로 말하기 → AI가 자동 분류
• /tasks - 전체 할 일 목록
• /today - 오늘 할 일만 보기
• /done `번호` - 완료 처리
• /progress `번호` - 진행 중으로 변경

**프로젝트 관리**
• /wbs `프로젝트 설명` - WBS 자동 생성
• /projects - 프로젝트 목록

**리마인더**
• "내일 3시에 알려줘" 식으로 말하면 자동 설정

**Google 연동**
• /google - Google 계정 연결
• 연결하면 Calendar, Tasks, Sheets 자동 동기화

**통계**
• /stats - 완료율, 진행 현황

**팁**: 부담 느끼지 마세요!
"일단 5분만" 하면 됩니다 😊"""

    await update.message.reply_text(help_text, parse_mode="Markdown")


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = db.get_tasks(user_id, status="pending")
    in_progress = db.get_tasks(user_id, status="in_progress")

    text = "**🔄 진행 중:**\n"
    text += _format_task_list(in_progress) if in_progress else "없음\n"
    text += "\n\n**⬜ 할 일:**\n"
    text += _format_task_list(tasks)

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = db.get_today_tasks(user_id)

    if not tasks:
        await update.message.reply_text("오늘은 할 일이 없어요! 푹 쉬세요 🌿")
        return

    text = "**☀️ 오늘의 할 일:**\n\n"
    text += _format_task_list(tasks)
    text += "\n\n💡 가장 쉬운 것부터 하나만 시작해볼까요?"

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("완료할 태스크 번호를 알려주세요!\n예: /done 3")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("숫자로 알려주세요! 예: /done 3")
        return

    task = db.get_task(task_id)
    if not task or task["user_id"] != user_id:
        await update.message.reply_text("해당 태스크를 찾을 수 없어요 🤔")
        return

    db.complete_task(task_id)

    # Google 동기화
    if google_service.is_connected(user_id):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        google_service.update_sheet_status(user_id, task["title"], "done", now)

    # 축하 메시지
    stats = db.get_stats(user_id)
    done_count = stats["done"]
    messages = [
        f"✅ **{task['title']}** 완료!\n\n잘했어요! 👏",
        f"✅ **{task['title']}** 완료!\n\n대단해요, 총 {done_count}개 완료했어요! 🎉",
        f"✅ **{task['title']}** 완료!\n\n멋져요! 이 기세 좋은데요? 💪",
    ]
    import random
    await update.message.reply_text(random.choice(messages), parse_mode="Markdown")

    # 하위 태스크가 있으면 다음 걸 제안
    subtasks = db.get_subtasks(task.get("parent_id") or task_id)
    pending_subs = [s for s in subtasks if s["status"] == "pending"]
    if pending_subs:
        next_task = pending_subs[0]
        keyboard = [
            [InlineKeyboardButton(f"✅ 이것도 할래요", callback_data=f"start_{next_task['id']}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"다음은 이건 어떨까요?\n➡️ **{next_task['title']}**"
            + (f" (약 {next_task['estimated_min']}분)" if next_task.get("estimated_min") else ""),
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )


async def cmd_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("태스크 번호를 알려주세요!\n예: /progress 3")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("숫자로 알려주세요!")
        return

    task = db.get_task(task_id)
    if not task or task["user_id"] != user_id:
        await update.message.reply_text("해당 태스크를 찾을 수 없어요 🤔")
        return

    db.update_task_status(task_id, "in_progress")
    await update.message.reply_text(
        f"🔄 **{task['title']}** 시작!\n\n화이팅! 일단 5분만 해보자는 마음으로 💪",
        parse_mode="Markdown",
    )


async def cmd_wbs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "프로젝트 설명을 알려주세요!\n예: /wbs 쇼핑몰 웹사이트 리뉴얼"
        )
        return

    project_desc = " ".join(context.args)
    await update.message.reply_text("🔨 WBS를 만들고 있어요... 잠시만요!")

    wbs = ai_service.generate_wbs(project_desc)
    if not wbs:
        await update.message.reply_text("WBS 생성에 문제가 있었어요. 다시 시도해주세요!")
        return

    # 프로젝트 생성
    project_id = db.create_project(user_id, wbs.get("project_name", project_desc))

    # WBS를 텍스트로 포매팅
    text = f"📊 **WBS: {wbs.get('project_name', project_desc)}**\n\n"

    for phase in wbs.get("phases", []):
        text += f"**📁 {phase['name']}**\n"

        for task in phase.get("tasks", []):
            # DB에 태스크 등록
            task_id = db.create_task(
                user_id=user_id,
                title=task["title"],
                project_id=project_id,
                estimated_min=task.get("estimated_min"),
            )

            est = f" ⏱️{task.get('estimated_min', '?')}분" if task.get("estimated_min") else ""
            text += f"  ├─ ⬜ `#{task_id}` {task['title']}{est}\n"

            # 서브태스크 등록
            for sub in task.get("subtasks", []):
                sub_id = db.create_task(
                    user_id=user_id,
                    title=sub["title"],
                    parent_id=task_id,
                    project_id=project_id,
                    estimated_min=sub.get("estimated_min"),
                )
                sub_est = f" ⏱️{sub.get('estimated_min', '?')}분" if sub.get("estimated_min") else ""
                text += f"  │  └─ ⬜ `#{sub_id}` {sub['title']}{sub_est}\n"

        text += "\n"

    text += f"\n{wbs.get('reply_message', '화이팅!')}"

    # Google Sheets에 기록
    if google_service.is_connected(user_id):
        for phase in wbs.get("phases", []):
            for task in phase.get("tasks", []):
                google_service.log_to_sheet(
                    user_id,
                    task_title=task["title"],
                    project_name=wbs.get("project_name", project_desc),
                    estimated_min=task.get("estimated_min", 0),
                )

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    projects = db.get_projects(user_id)

    if not projects:
        await update.message.reply_text("아직 프로젝트가 없어요. /wbs로 만들어보세요!")
        return

    text = "**📁 프로젝트 목록:**\n\n"
    for p in projects:
        task_count = len(db.get_tasks(user_id, project_id=p["id"]))
        done_count = len(db.get_tasks(user_id, status="done", project_id=p["id"]))
        text += f"• **{p['name']}** ({done_count}/{task_count} 완료)\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = db.get_stats(user_id)

    total = stats["total"] or 0
    done = stats["done"] or 0
    pending = stats["pending"] or 0
    in_progress = stats["in_progress"] or 0

    rate = round((done / total) * 100) if total > 0 else 0

    # 프로그레스 바
    filled = rate // 10
    bar = "█" * filled + "░" * (10 - filled)

    text = f"""**📊 나의 통계**

전체: {total}개
✅ 완료: {done}개
🔄 진행 중: {in_progress}개
⬜ 대기: {pending}개

**완료율:** {bar} {rate}%
"""

    if rate >= 80:
        text += "\n🏆 대단해요! 거의 다 했어요!"
    elif rate >= 50:
        text += "\n💪 절반 넘었어요! 잘하고 있어요!"
    elif done > 0:
        text += "\n🌱 시작이 반이에요! 잘하고 있어요!"
    else:
        text += "\n🌿 천천히 하나씩 해봐요!"

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_google(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if google_service.is_connected(user_id):
        await update.message.reply_text(
            "✅ 이미 Google 계정이 연결되어 있어요!\n"
            "태스크 생성 시 자동으로 Calendar, Tasks, Sheets에 동기화됩니다."
        )
        return

    if context.args:
        # 인증 코드 입력
        code = context.args[0]
        if google_service.exchange_code(user_id, code):
            await update.message.reply_text(
                "✅ Google 계정 연결 완료!\n\n"
                "이제부터 태스크가 자동으로 동기화됩니다:\n"
                "📅 Google Calendar\n"
                "✅ Google Tasks\n"
                "📊 Google Sheets"
            )
        else:
            await update.message.reply_text("❌ 인증에 실패했어요. 코드를 다시 확인해주세요.")
        return

    # 인증 URL 생성
    auth_url = google_service.get_auth_url(user_id)
    await update.message.reply_text(
        "**🔗 Google 계정 연결**\n\n"
        f"1. 아래 링크를 열어 Google 로그인하세요:\n{auth_url}\n\n"
        "2. 권한을 허용하면 코드가 표시됩니다\n"
        "3. 그 코드를 이렇게 보내주세요:\n"
        "`/google 여기에_코드_붙여넣기`",
        parse_mode="Markdown",
    )


# ── 자연어 메시지 처리 ──


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_message = update.message.text

    db.upsert_user(user.id, user.username, user.first_name)

    # AI에게 현재 컨텍스트와 함께 전달
    task_context = _task_context(user.id)
    result = ai_service.parse_user_input(user_message, context=task_context)

    action = result["action"]
    data = result["data"]

    if action == "create_tasks":
        reply = data.get("reply_message", "알겠어요!")
        tasks = data.get("tasks", [])

        created_tasks = []
        for t in tasks:
            # 메인 태스크 생성
            task_id = db.create_task(
                user_id=user.id,
                title=t["title"],
                description=t.get("description"),
                deadline=t.get("deadline"),
                priority=t.get("priority", 2),
                estimated_min=t.get("estimated_min"),
            )
            created_tasks.append((task_id, t))

            # 서브태스크 생성
            for sub in t.get("subtasks", []):
                db.create_task(
                    user_id=user.id,
                    title=sub["title"],
                    parent_id=task_id,
                    estimated_min=sub.get("estimated_min"),
                )

            # Google 동기화
            await _sync_to_google(
                user.id,
                title=t["title"],
                deadline=t.get("deadline"),
                description=t.get("description"),
            )

        # 응답 메시지 구성
        text = f"{reply}\n\n"
        for task_id, t in created_tasks:
            text += f"📝 `#{task_id}` **{t['title']}**\n"
            if t.get("deadline"):
                text += f"   📅 마감: {t['deadline'][:16]}\n"
            if t.get("estimated_min"):
                text += f"   ⏱️ 예상: {t['estimated_min']}분\n"

            subtasks = t.get("subtasks", [])
            if subtasks:
                text += "   📋 세부 단계:\n"
                for i, sub in enumerate(subtasks, 1):
                    est = f" ({sub.get('estimated_min', '?')}분)" if sub.get("estimated_min") else ""
                    text += f"   {i}. {sub['title']}{est}\n"
            text += "\n"

        # 첫 번째 태스크 시작 제안
        if created_tasks:
            first_id, first_task = created_tasks[0]
            subs = first_task.get("subtasks", [])
            if subs:
                text += f"💡 일단 첫 단계부터 해볼까요?\n➡️ {subs[0]['title']}"
            else:
                text += "💡 바로 시작해볼까요?"

        await update.message.reply_text(text, parse_mode="Markdown")

    elif action == "reply":
        await update.message.reply_text(data.get("message", ""))


# ── 콜백 쿼리 (인라인 버튼) ──


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id

    if data.startswith("start_"):
        task_id = int(data.split("_")[1])
        task = db.get_task(task_id)
        if task and task["user_id"] == user_id:
            db.update_task_status(task_id, "in_progress")
            await query.edit_message_text(
                f"🔄 **{task['title']}** 시작!\n화이팅! 일단 5분만 해보자 💪",
                parse_mode="Markdown",
            )


# ── 에러 핸들러 ──


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "앗, 잠깐 문제가 있었어요. 다시 한번 말씀해주세요! 🙏"
        )


# ── 메인 ──


def main():
    db.init_db()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # 명령어 핸들러
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(CommandHandler("progress", cmd_progress))
    app.add_handler(CommandHandler("wbs", cmd_wbs))
    app.add_handler(CommandHandler("projects", cmd_projects))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("google", cmd_google))

    # 자연어 메시지 핸들러
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 콜백 쿼리 핸들러
    app.add_handler(CallbackQueryHandler(handle_callback))

    # 에러 핸들러
    app.add_error_handler(error_handler)

    # 스케줄러 시작
    scheduler.set_bot(app.bot)
    scheduler.start_scheduler()

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
