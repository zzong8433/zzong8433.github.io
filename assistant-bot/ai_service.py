"""
AI Service - Google Gemini API를 활용한 자연어 처리 & ADHD 맞춤 비서
"""
import json
import os
from datetime import datetime, timedelta

import google.generativeai as genai

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

MODEL = os.environ.get("AI_MODEL", "gemini-2.0-flash")

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

현재 날짜/시간: {current_time}
"""

# ── Gemini Function Declarations ──

CREATE_TASKS_FUNC = genai.protos.FunctionDeclaration(
    name="create_tasks",
    description="사용자의 자연어 입력을 분석해서 태스크를 생성합니다",
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "reply_message": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="사용자에게 보낼 따뜻한 응답 메시지 (한국어, ADHD 친화적)",
            ),
            "tasks": genai.protos.Schema(
                type=genai.protos.Type.ARRAY,
                items=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        "title": genai.protos.Schema(type=genai.protos.Type.STRING, description="태스크 제목"),
                        "description": genai.protos.Schema(type=genai.protos.Type.STRING, description="태스크 설명"),
                        "deadline": genai.protos.Schema(
                            type=genai.protos.Type.STRING,
                            description="마감일 ISO 형식 (YYYY-MM-DDTHH:MM:SS) 또는 빈 문자열",
                        ),
                        "priority": genai.protos.Schema(
                            type=genai.protos.Type.INTEGER,
                            description="우선순위 1(높음)~3(낮음)",
                        ),
                        "estimated_min": genai.protos.Schema(
                            type=genai.protos.Type.INTEGER,
                            description="예상 소요시간 (분)",
                        ),
                        "subtasks": genai.protos.Schema(
                            type=genai.protos.Type.ARRAY,
                            items=genai.protos.Schema(
                                type=genai.protos.Type.OBJECT,
                                properties={
                                    "title": genai.protos.Schema(type=genai.protos.Type.STRING),
                                    "estimated_min": genai.protos.Schema(type=genai.protos.Type.INTEGER),
                                },
                                required=["title"],
                            ),
                            description="ADHD 친화적으로 세분화된 하위 태스크들 (5~15분 단위)",
                        ),
                    },
                    required=["title"],
                ),
            ),
        },
        required=["reply_message", "tasks"],
    ),
)

REPLY_FUNC = genai.protos.FunctionDeclaration(
    name="reply",
    description="사용자에게 일반 대화로 응답합니다 (업무 관련이 아닌 일반 대화)",
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "message": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="사용자에게 보낼 응답 (한국어, 따뜻하고 ADHD 친화적)",
            ),
        },
        required=["message"],
    ),
)

GENERATE_WBS_FUNC = genai.protos.FunctionDeclaration(
    name="generate_wbs",
    description="프로젝트의 WBS(Work Breakdown Structure)를 생성합니다",
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "reply_message": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                description="사용자에게 보낼 격려 메시지",
            ),
            "project_name": genai.protos.Schema(type=genai.protos.Type.STRING),
            "phases": genai.protos.Schema(
                type=genai.protos.Type.ARRAY,
                items=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        "name": genai.protos.Schema(type=genai.protos.Type.STRING, description="단계 이름"),
                        "tasks": genai.protos.Schema(
                            type=genai.protos.Type.ARRAY,
                            items=genai.protos.Schema(
                                type=genai.protos.Type.OBJECT,
                                properties={
                                    "title": genai.protos.Schema(type=genai.protos.Type.STRING),
                                    "estimated_min": genai.protos.Schema(type=genai.protos.Type.INTEGER),
                                    "subtasks": genai.protos.Schema(
                                        type=genai.protos.Type.ARRAY,
                                        items=genai.protos.Schema(
                                            type=genai.protos.Type.OBJECT,
                                            properties={
                                                "title": genai.protos.Schema(type=genai.protos.Type.STRING),
                                                "estimated_min": genai.protos.Schema(type=genai.protos.Type.INTEGER),
                                            },
                                            required=["title"],
                                        ),
                                    ),
                                },
                                required=["title"],
                            ),
                        ),
                    },
                    required=["name", "tasks"],
                ),
            ),
        },
        required=["reply_message", "project_name", "phases"],
    ),
)

PARSE_TOOLS = genai.protos.Tool(function_declarations=[CREATE_TASKS_FUNC, REPLY_FUNC])
WBS_TOOLS = genai.protos.Tool(function_declarations=[GENERATE_WBS_FUNC])


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M (%A)")


def _extract_function_call(response) -> dict | None:
    """Gemini 응답에서 function call 추출"""
    for candidate in response.candidates:
        for part in candidate.content.parts:
            if part.function_call.name:
                # proto MapComposite를 일반 dict로 변환
                args = dict(part.function_call.args)
                # 중첩된 proto 객체들도 변환
                args = _proto_to_dict(args)
                return {"name": part.function_call.name, "args": args}
    return None


def _proto_to_dict(obj):
    """Proto MapComposite / RepeatedComposite를 순수 Python dict/list로 변환"""
    if hasattr(obj, "items"):
        return {k: _proto_to_dict(v) for k, v in obj.items()}
    elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
        return [_proto_to_dict(item) for item in obj]
    else:
        return obj


def parse_user_input(user_message: str, context: str = "") -> dict:
    """사용자의 자연어 입력을 분석해서 태스크 생성 또는 일반 대화로 분류"""
    system = SYSTEM_PROMPT.format(current_time=_now_str())
    if context:
        system += f"\n\n## 현재 사용자의 태스크 상황:\n{context}"

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=system,
        tools=[PARSE_TOOLS],
    )

    response = model.generate_content(
        user_message,
        tool_config=genai.types.content_types.to_tool_config({
            "function_calling_config": {"mode": "ANY"},
        }),
    )

    fc = _extract_function_call(response)
    if fc:
        return {"action": fc["name"], "data": fc["args"]}

    return {"action": "reply", "data": {"message": "무슨 말인지 이해했어요! 좀 더 자세히 알려주시겠어요?"}}


def generate_wbs(project_description: str) -> dict:
    """프로젝트 설명으로부터 WBS를 생성"""
    system = SYSTEM_PROMPT.format(current_time=_now_str())

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=system,
        tools=[WBS_TOOLS],
    )

    response = model.generate_content(
        f"다음 프로젝트의 WBS를 만들어줘. ADHD 특성을 고려해서 작은 단위로 쪼개줘:\n\n{project_description}",
        tool_config=genai.types.content_types.to_tool_config({
            "function_calling_config": {"mode": "ANY"},
        }),
    )

    fc = _extract_function_call(response)
    if fc:
        return fc["args"]

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

    model = genai.GenerativeModel(
        MODEL,
        system_instruction="당신은 ADHD 특성을 이해하는 따뜻한 업무 비서입니다. 한국어로 응답하세요.",
    )

    response = model.generate_content(prompt)
    return response.text


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

    model = genai.GenerativeModel(
        MODEL,
        system_instruction="당신은 ADHD 특성을 이해하는 따뜻한 업무 비서입니다. 한국어로 응답하세요.",
    )

    response = model.generate_content(prompt)
    return response.text
