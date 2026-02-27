# ADHD 어시스턴트 플레이북

> Claude Code를 ADHD 코칭 에이전트로 쓰는 방법
> 별도 앱 개발 필요 없음. 설정만 하면 끝.

---

## 핵심 아이디어

Claude Code 터미널 자체를 **상시 대화형 ADHD 코칭 어시스턴트**로 쓴다.

- AI 대화: Claude Code에 이미 내장
- 태스크 관리: 파일 읽기/쓰기로 해결
- 캘린더 연동: MCP 서버로 연결
- 데이터 보존: iCloud 동기화 폴더에 저장
- 성격/컨텍스트: `CLAUDE.md` 파일 하나로 설정

**봇 서버도, DB도, 배포도 필요 없다.**

---

## 아키텍처

```
Claude Code (터미널 or 리모트)
│
├── CLAUDE.md ─────────── 성격 + 규칙 + 컨텍스트
│
├── MCP 서버들
│   ├── Google Calendar ── 일정 읽기/쓰기
│   ├── Google Drive ───── 문서 접근 (선택)
│   └── (필요시 추가) ──── Notion, Slack 등
│
├── iCloud 동기화 폴더 ── 모든 기록 저장
│   ├── daily/ ─────────── 매일 할일
│   ├── projects/ ──────── 프로젝트별 태스크
│   ├── reviews/ ───────── 회고록
│   └── brain-dump/ ────── 아무거나 던지는 곳
│
└── TodoWrite ─────────── 실시간 태스크 분해
```

---

## 세팅 가이드

### Step 1: iCloud 폴더 구조 만들기 (2분)

```bash
BASE=~/Library/Mobile\ Documents/com~apple~CloudDocs/adhd-assistant

mkdir -p "$BASE/daily"
mkdir -p "$BASE/projects"
mkdir -p "$BASE/reviews"
mkdir -p "$BASE/brain-dump"
```

> iCloud 말고 Google Drive, Dropbox 등 아무 클라우드 동기화 폴더 써도 됨.
> 핵심은 "파일이 클라우드에 동기화되어 안 잃어버린다"는 것.

---

### Step 2: CLAUDE.md 작성 (5분)

프로젝트 루트 또는 홈 디렉토리에 `CLAUDE.md` 파일을 만든다.
Claude Code는 세션 시작 시 이 파일을 자동으로 읽는다.

```markdown
# ADHD 코칭 어시스턴트

## 너의 역할
- 나는 ADHD가 있어서 큰 작업을 시작하기 어렵다
- 너는 나의 코칭 어시스턴트다
- 모든 기록은 ~/Library/Mobile Documents/com~apple~CloudDocs/adhd-assistant/ 에 저장

## 핵심 규칙
1. **한 번에 하나만**: 절대 여러 개를 동시에 시키지 마
2. **작게 쪼개기**: 15분 이내로 끝낼 수 있는 단위로
3. **즉시 기록**: 내가 말하는 건 뭐든 바로 파일에 저장
4. **칭찬 먼저**: 뭘 완료하면 인정해주고, 다음 단계 제시
5. **부드럽게 리다이렉트**: 딴소리 하면 자연스럽게 다시 본론으로

## 매일 루틴
- 세션 시작하면 오늘 daily 파일 확인하거나 새로 만들기
- 파일명 형식: daily/YYYY-MM-DD.md
- 어제 미완료 항목이 있으면 오늘로 옮길지 물어보기

## 태스크 분해 규칙
- 큰 목표 → 중간 목표 (프로젝트) → 오늘 할 것 → 지금 할 것
- "지금 할 것"은 반드시 구체적 행동으로 (예: "보고서 쓰기" ❌ → "보고서 1페이지 서론 3줄 쓰기" ✅)

## 브레인덤프 모드
- 내가 "덤프" 또는 "dump"라고 하면 브레인덤프 모드
- 내가 말하는 것 그대로 brain-dump/ 폴더에 타임스탬프와 함께 저장
- 정리하지 말고 원문 그대로 저장
- 나중에 내가 정리해달라고 하면 그때 정리

## 주간 회고
- 일요일에 세션 열면 주간 회고 제안
- 이번 주 완료한 것 / 못한 것 / 다음 주 계획 정리
- reviews/ 폴더에 저장

## 파일 형식
daily 파일 예시:
---
# 2026-02-27 (금)

## 오늘 목표
- [ ] 프로젝트 A 1페이지 작성
- [ ] 이메일 3개 답장

## 완료
- [x] 아침 루틴

## 메모
- 오후에 집중 잘 됐음
---
```

> 이건 예시이므로 자기 스타일에 맞게 수정할 것.

---

### Step 3: MCP 서버 설정 (10분)

`~/.claude/settings.json` 또는 프로젝트의 `.mcp.json`에 추가:

#### Google Calendar MCP

```bash
# 먼저 설치
npm install -g @anthropic/mcp-google-calendar
```

```json
{
  "mcpServers": {
    "google-calendar": {
      "command": "npx",
      "args": ["@anthropic/mcp-google-calendar"],
      "env": {
        "GOOGLE_CLIENT_ID": "너의_클라이언트_ID",
        "GOOGLE_CLIENT_SECRET": "너의_시크릿",
        "GOOGLE_REDIRECT_URI": "http://localhost:3000/callback"
      }
    }
  }
}
```

> MCP 서버는 계속 추가 가능: Notion, Slack, Linear, GitHub 등
> 공식 목록: https://github.com/anthropics/mcp-servers

---

### Step 4: 사용하기

터미널 열고:

```bash
# iCloud 폴더로 이동해서 Claude Code 실행
cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/adhd-assistant
claude
```

그리고 그냥 말하면 됨:

```
나: 오늘 뭐 해야 하지?
Claude: (daily 파일 확인하고 알려줌)

나: 프로젝트 A 너무 커서 뭐부터 해야 할지 모르겠어
Claude: (작은 단계로 쪼개서 제안, 파일에 저장)

나: dump - 갑자기 생각난 건데 다음 달에 여행 가고 싶고...
Claude: (brain-dump 폴더에 원문 그대로 저장)

나: 이메일 답장 완료!
Claude: (체크 표시, 칭찬, 다음 할 일 제안)
```

---

## 장점

| 항목 | 설명 |
|------|------|
| 개발 비용 | 0. 설정 파일만 쓰면 끝 |
| AI 품질 | Claude 최신 모델 그대로 사용 |
| 확장성 | MCP 서버 추가로 무한 확장 |
| 데이터 보존 | iCloud/GDrive 동기화 = 영구 보존 |
| 커스텀 | CLAUDE.md 수정만으로 성격/규칙 변경 |
| 유지보수 | 없음. 코드가 없으니까 |

## 한계 (솔직하게)

| 항목 | 설명 | 대안 |
|------|------|------|
| 세션 끊김 | 터미널 닫으면 대화 맥락 사라짐 | 파일에 기록하니까 새 세션에서 읽으면 복구 |
| 모바일 접근 | Mac 앞에 있어야 함 | 폰에서는 iCloud 파일로 확인만 가능 |
| 알림 없음 | 푸시 알림 못 보냄 | Apple 리마인더 앱과 병행 |
| 항상 켜야 함 | 24시간 서버가 아님 | Claude Code 리모트 사용 시 해결 가능 |

---

## 발전 로드맵

### v1 (지금 당장)
- [x] CLAUDE.md 작성
- [x] iCloud 폴더 구조 생성
- [ ] 실제로 1주일 써보기

### v2 (쓰다 보면 필요해지는 것들)
- [ ] Google Calendar MCP 연결
- [ ] 주간 회고 템플릿 다듬기
- [ ] 자주 쓰는 명령어 숏컷 만들기 (alias)

### v3 (고도화)
- [ ] 텔레그램 봇 연동 (모바일 접근용, 필요시에만)
- [ ] 습관 트래커 추가
- [ ] 데이터 기반 패턴 분석 ("너 목요일 오후에 집중 잘 하더라")

---

## 한 줄 요약

> **Claude Code + CLAUDE.md + iCloud 폴더 = 개발 0으로 만드는 ADHD 어시스턴트**
>
> 코드 짤 필요 없다. 설정만 하면 된다.
> 데이터는 클라우드에 동기화되니까 잃어버릴 일 없다.
> 부족하면 나중에 MCP 서버 추가하면 된다.
