"""
Google 연동 서비스 - Calendar, Tasks, Sheets
OAuth2 인증 후 태스크 생성 시 자동으로 Google에 동기화
"""
import json
import os
import logging
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/spreadsheets",
]

# 환경변수에서 Google OAuth 클라이언트 정보 로드
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob")

# 토큰 저장 경로 (user_id별)
TOKEN_DIR = os.environ.get("TOKEN_DIR", "tokens")

# Google Sheets 설정
SPREADSHEET_ID = os.environ.get("GOOGLE_SPREADSHEET_ID", "")


def _get_client_config() -> dict:
    return {
        "installed": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uris": [GOOGLE_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def _token_path(user_id: int) -> str:
    os.makedirs(TOKEN_DIR, exist_ok=True)
    return os.path.join(TOKEN_DIR, f"{user_id}.json")


def get_auth_url(user_id: int) -> str:
    """Google OAuth 인증 URL 생성"""
    flow = Flow.from_client_config(_get_client_config(), scopes=SCOPES)
    flow.redirect_uri = GOOGLE_REDIRECT_URI

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=str(user_id),
    )
    return auth_url


def exchange_code(user_id: int, code: str) -> bool:
    """인증 코드를 토큰으로 교환 후 저장"""
    try:
        flow = Flow.from_client_config(_get_client_config(), scopes=SCOPES)
        flow.redirect_uri = GOOGLE_REDIRECT_URI
        flow.fetch_token(code=code)

        creds = flow.credentials
        with open(_token_path(user_id), "w") as f:
            f.write(creds.to_json())

        return True
    except Exception as e:
        logger.error(f"Token exchange failed for user {user_id}: {e}")
        return False


def _get_credentials(user_id: int) -> Credentials | None:
    """저장된 토큰을 로드하고 필요시 갱신"""
    path = _token_path(user_id)
    if not os.path.exists(path):
        return None

    try:
        creds = Credentials.from_authorized_user_file(path, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(path, "w") as f:
                f.write(creds.to_json())
        return creds
    except Exception as e:
        logger.error(f"Failed to load credentials for user {user_id}: {e}")
        return None


def is_connected(user_id: int) -> bool:
    """Google 계정 연결 여부 확인"""
    return _get_credentials(user_id) is not None


# ── Google Calendar ──


def add_to_calendar(
    user_id: int,
    title: str,
    deadline: str = None,
    description: str = None,
) -> str | None:
    """Google Calendar에 이벤트 추가. 이벤트 ID 반환."""
    creds = _get_credentials(user_id)
    if not creds:
        return None

    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        if deadline:
            dt = datetime.fromisoformat(deadline)
            start = (dt - timedelta(hours=1)).isoformat()
            end = dt.isoformat()
            event_body = {
                "summary": f"📋 {title}",
                "description": description or "",
                "start": {"dateTime": start, "timeZone": "Asia/Seoul"},
                "end": {"dateTime": end, "timeZone": "Asia/Seoul"},
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 60},
                        {"method": "popup", "minutes": 15},
                    ],
                },
            }
        else:
            today = datetime.now().strftime("%Y-%m-%d")
            event_body = {
                "summary": f"📋 {title}",
                "description": description or "",
                "start": {"date": today},
                "end": {"date": today},
            }

        event = service.events().insert(calendarId="primary", body=event_body).execute()
        logger.info(f"Calendar event created: {event.get('id')}")
        return event.get("id")
    except Exception as e:
        logger.error(f"Failed to create calendar event: {e}")
        return None


def remove_from_calendar(user_id: int, event_id: str) -> bool:
    """Google Calendar에서 이벤트 삭제"""
    creds = _get_credentials(user_id)
    if not creds:
        return False

    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to delete calendar event: {e}")
        return False


# ── Google Tasks ──


def add_to_google_tasks(
    user_id: int,
    title: str,
    deadline: str = None,
    notes: str = None,
) -> str | None:
    """Google Tasks에 태스크 추가. 태스크 ID 반환."""
    creds = _get_credentials(user_id)
    if not creds:
        return None

    try:
        service = build("tasks", "v1", credentials=creds, cache_discovery=False)

        task_body = {"title": title, "notes": notes or ""}
        if deadline:
            # Google Tasks는 RFC 3339 날짜 형식 필요
            dt = datetime.fromisoformat(deadline)
            task_body["due"] = dt.strftime("%Y-%m-%dT00:00:00.000Z")

        # 기본 태스크 리스트 사용
        task = service.tasks().insert(tasklist="@default", body=task_body).execute()
        logger.info(f"Google Task created: {task.get('id')}")
        return task.get("id")
    except Exception as e:
        logger.error(f"Failed to create Google Task: {e}")
        return None


def complete_google_task(user_id: int, task_id: str) -> bool:
    """Google Tasks에서 태스크 완료 처리"""
    creds = _get_credentials(user_id)
    if not creds:
        return False

    try:
        service = build("tasks", "v1", credentials=creds, cache_discovery=False)
        service.tasks().patch(
            tasklist="@default",
            task=task_id,
            body={"status": "completed"},
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to complete Google Task: {e}")
        return False


# ── Google Sheets (업무 로그) ──


def _ensure_sheet_headers(service, spreadsheet_id: str):
    """시트에 헤더가 없으면 추가"""
    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range="A1:J1")
            .execute()
        )
        if not result.get("values"):
            headers = [
                ["날짜", "시간", "태스크", "설명", "프로젝트", "마감일", "우선순위", "상태", "예상시간(분)", "완료일시"]
            ]
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="A1:J1",
                valueInputOption="RAW",
                body={"values": headers},
            ).execute()
    except Exception as e:
        logger.error(f"Failed to ensure sheet headers: {e}")


def log_to_sheet(
    user_id: int,
    task_title: str,
    description: str = "",
    project_name: str = "",
    deadline: str = "",
    priority: int = 2,
    status: str = "pending",
    estimated_min: int = 0,
    completed_at: str = "",
) -> bool:
    """Google Sheets에 태스크 로그 기록"""
    if not SPREADSHEET_ID:
        logger.warning("GOOGLE_SPREADSHEET_ID not set, skipping sheet logging")
        return False

    creds = _get_credentials(user_id)
    if not creds:
        return False

    try:
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        _ensure_sheet_headers(service, SPREADSHEET_ID)

        now = datetime.now()
        priority_labels = {1: "높음", 2: "보통", 3: "낮음"}

        row = [
            [
                now.strftime("%Y-%m-%d"),
                now.strftime("%H:%M:%S"),
                task_title,
                description,
                project_name,
                deadline,
                priority_labels.get(priority, "보통"),
                status,
                str(estimated_min) if estimated_min else "",
                completed_at,
            ]
        ]

        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="A:J",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": row},
        ).execute()

        logger.info(f"Task logged to sheet: {task_title}")
        return True
    except Exception as e:
        logger.error(f"Failed to log to sheet: {e}")
        return False


def update_sheet_status(
    user_id: int,
    task_title: str,
    new_status: str,
    completed_at: str = "",
) -> bool:
    """Google Sheets에서 태스크 상태 업데이트"""
    if not SPREADSHEET_ID:
        return False

    creds = _get_credentials(user_id)
    if not creds:
        return False

    try:
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)

        # 해당 태스크를 찾기
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=SPREADSHEET_ID, range="A:J")
            .execute()
        )
        values = result.get("values", [])

        for i, row in enumerate(values):
            if len(row) > 2 and row[2] == task_title:
                # 상태 컬럼(H=8번째) 업데이트
                row_num = i + 1
                service.spreadsheets().values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"H{row_num}:J{row_num}",
                    valueInputOption="RAW",
                    body={"values": [[new_status, "", completed_at]]},
                ).execute()
                return True

        return False
    except Exception as e:
        logger.error(f"Failed to update sheet status: {e}")
        return False
