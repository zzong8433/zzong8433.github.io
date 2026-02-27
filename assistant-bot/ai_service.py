"""
AI Service - Claude API를 활용한 자연어 처리 & ADHD 맞춤 비서
"""
import json
import os
from datetime import datetime, timedelta

import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

MODEL_FAST = "claude-haiku-4-5-20251001"      # 일상 대화, 태스크 파싱 (저렴, 빠름)
MODEL_SMART = "claude-sonnet-4-5-20250514"     # WBS 생성, 복잡한 분석 (정확, 비쌈)

# 사용자별 수동 오버라이드 저장 (user_id → model)
_user_model_override: dict[int, str] = {}


def get_model(user_id: int = 0, task_type: str = "fast") -> str:
    """사용자별 모델 반환. 수동 오버라이드 > 태스크 타입별 자동 선택"""
    override = _user_model_override.get(user_id)
    if override:
        return override
    return MODEL_SMART if task_type == "smart" else MODEL_FAST


def set_user_model(user_id: int, model: str | None):
    """사용자별 모델 수동 설정. None이면 자동 모드로 복귀"""
    if model is None:
        _user_model_override.pop(user_id, None)
    else:
        _user_model_override[user_id] = model


def get_user_model_info(user_id: int) -> str:
    """현재 사용자의 모델 설정 정보 반환"""
    override = _user_model_override.get(user_id)
    if override:
        name = "Sonnet (똑똑)" if "sonnet" in override else "Haiku (빠름)"
        return f"수동 고정: {name}"
    return "자동 (평소 Haiku, WBS는 Sonnet)"

SYSTEM_PROMPT = """당신은 ADHD 특성을 깊이 이해하는 따뜻한 업무 비서입니다.

## 핵심 원칙
1. **업무를 작게 쪼개기**: 모든 업무를 5~15분 단위의 작은 단계로 나눕니다
2. **부드럽고 격려하는 톤**: 절대 재촉하거나 비난하지 않습니다
3. **구체적인 다음 행동**: "보고서 쓰기" 대신 "보고서 1페이지 개요 3줄 적기"처럼 구체적으로
4. **작은 성취 축하**: 완료할 때마다 진심으로 칭찬합니다
5. **부담 줄이기**: "일단 5분만 해보자"식의 접근

## 데드라인 설정 기준
- 사용자가 명시하면 그대로 사용
- "이번 주" → 이번 주 금요일 18:00
- "다음 주" → 다음 주 금요일 18:00
- "오늘" → 오늘 23:59
- "내일" → 내일 18:00
- 명시하지 않으면 null

## WBS 생성 기준
- 최상위 업무를 3~5개 중간 단계로 나눔
- 각 중간 단계를 2~4개 세부 단계로 나눔
- 각 세부 단계의 예상 소요시간을 5~30분 단위로 설정
- ADHD 특성 고려: 시작이 쉬운 것을 앞에 배치

## 응답 형식
반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 반환하세요.

현재 날짜/시간: {current_time}
"""

PARSE_TASK_TOOLS = [
    {
        "name": "create_tasks",
        "description": "사용자의 자연어 입력을 분석해서 태스크를 생성합니다",
        "input_schema": {
            "type": "object",
            "properties": {
                "reply_message": {
                    "type": "string",
                    "description": "사용자에게 보낼 따뜻한 응답 메시지 (한국어, ADHD 친화적)",
                },
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "태스크 제목"},
                            "description": {"type": "string", "description": "태스크 설명"},
                            "deadline": {
                                "type": "string",
                                "description": "마감일 ISO 형식 (YYYY-MM-DDTHH:MM:SS) 또는 null",
                            },
                            "priority": {
                                "type": "integer",
                                "description": "우선순위 1(높음)~3(낮음)",
                                "enum": [1, 2, 3],
                            },
                            "estimated_min": {
                                "type": "integer",
                                "description": "예상 소요시간 (분)",
                            },
                            "subtasks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"},
                                        "estimated_min": {"type": "integer"},
                                    },
                                    "required": ["title"],
                                },
                                "description": "ADHD 친화적으로 세분화된 하위 태스크들 (5~15분 단위)",
                            },
                        },
                        "required": ["title"],
                    },
                },
            },
            "required": ["reply_message", "tasks"],
        },
    }
]

WBS_TOOL = [
    {
        "name": "generate_wbs",
        "description": "프로젝트의 WBS(Work Breakdown Structure)를 생성합니다",
        "input_schema": {
            "type": "object",
            "properties": {
                "reply_message": {
                    "type": "string",
                    "description": "사용자에게 보낼 격려 메시지",
                },
                "project_name": {"type": "string"},
                "phases": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "단계 이름"},
                            "tasks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"},
                                        "estimated_min": {"type": "integer"},
                                        "subtasks": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "title": {"type": "string"},
                                                    "estimated_min": {"type": "integer"},
                                                },
                                                "required": ["title"],
                                            },
                                        },
                                    },
                                    "required": ["title"],
                                },
                            },
                        },
                        "required": ["name", "tasks"],
                    },
                },
            },
            "required": ["reply_message", "project_name", "phases"],
        },
    }
]

CHAT_TOOL = [
    {
        "name": "reply",
        "description": "사용자에게 일반 대화로 응답합니다",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "사용자에게 보낼 응답 (한국어, 따뜻하고 ADHD 친화적)",
                },
            },
            "required": ["message"],
        },
    }
]


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M (%A)")


def parse_user_input(user_message: str, context: str = "", user_id: int = 0) -> dict:
    """사용자의 자연어 입력을 분석해서 태스크 생성 또는 일반 대화로 분류"""
    system = SYSTEM_PROMPT.format(current_time=_now_str())
    if context:
        system += f"\n\n## 현재 사용자의 태스크 상황:\n{context}"

    messages = [{"role": "user", "content": user_message}]

    response = client.messages.create(
        model=get_model(user_id, "fast"),
        max_tokens=2048,
        system=system,
        messages=messages,
        tools=PARSE_TASK_TOOLS + CHAT_TOOL,
        tool_choice={"type": "any"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return {"action": block.name, "data": block.input}

    return {"action": "reply", "data": {"message": "무슨 말인지 이해했어요! 좀 더 자세히 알려주시겠어요?"}}


def generate_wbs(project_description: str, user_id: int = 0) -> dict:
    """프로젝트 설명으로부터 WBS를 생성 (자동으로 Sonnet 사용)"""
    system = SYSTEM_PROMPT.format(current_time=_now_str())

    messages = [
        {
            "role": "user",
            "content": f"다음 프로젝트의 WBS를 만들어줘. ADHD 특성을 고려해서 작은 단위로 쪼개줘:\n\n{project_description}",
        }
    ]

    response = client.messages.create(
        model=get_model(user_id, "smart"),
        max_tokens=4096,
        system=system,
        messages=messages,
        tools=WBS_TOOL,
        tool_choice={"type": "tool", "name": "generate_wbs"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    return None


def generate_daily_message(tasks: list[dict], stats: dict) -> str:
    """오늘의 요약 + 격려 메시지 생성"""
    task_info = ""
    for t in tasks:
        deadline_str = f" (마감: {t['deadline']})" if t.get("deadline") else ""
        task_info += f"- {t['title']}{deadline_str} [{t['status']}]\n"

    if not task_info:
        task_info = "(오늘 할 일이 없습니다)"

    prompt = f"""오늘의 태스크 목록:
{task_info}

통계: 전체 {stats.get('total', 0)}개 중 {stats.get('done', 0)}개 완료, {stats.get('pending', 0)}개 대기 중

위 정보를 바탕으로 사용자에게 오늘의 아침 브리핑 메시지를 작성해주세요.
- ADHD 특성 고려: 부담스럽지 않게, "일단 하나만 해보자" 식으로
- 가장 쉬운/짧은 태스크를 먼저 추천
- 격려와 칭찬을 곁들여서
- 이모지 적절히 사용
- 200자 이내로 간결하게
"""

    response = client.messages.create(
        model=MODEL_FAST,
        max_tokens=512,
        system="당신은 ADHD 특성을 이해하는 따뜻한 업무 비서입니다. 한국어로 응답하세요.",
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def generate_nudge_message(task: dict) -> str:
    """부드러운 리마인더 메시지 생성"""
    prompt = f"""이 태스크에 대한 부드러운 리마인더 메시지를 작성해주세요:
- 태스크: {task['title']}
- 마감: {task.get('deadline', '없음')}

규칙:
- 절대 재촉하는 느낌 금지
- "혹시 이거 5분만 해볼까요?" 식으로 부드럽게
- ADHD 특성 고려
- 100자 이내
"""

    response = client.messages.create(
        model=MODEL_FAST,
        max_tokens=256,
        system="당신은 ADHD 특성을 이해하는 따뜻한 업무 비서입니다. 한국어로 응답하세요.",
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text
