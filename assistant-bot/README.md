# 🧠 ADHD 친화 업무 비서 (텔레그램 봇)

자연어로 업무를 말하면 AI가 자동으로 세분화해주는 ADHD 맞춤 업무 비서입니다.

## 주요 기능

| 기능 | 설명 |
|------|------|
| 🗣️ 자연어 입력 | "다음 주까지 보고서 써야 해" → 자동 태스크 생성 |
| 📊 WBS 생성 | 프로젝트를 작은 단위로 자동 분해 |
| ⏰ 스마트 리마인더 | 매일 아침 브리핑 + 마감 임박 부드러운 알림 |
| 📅 Google Calendar | 일정 자동 동기화 |
| ✅ Google Tasks | 태스크 자동 동기화 |
| 📊 Google Sheets | 업무 히스토리 자동 기록 (업무일지/필터링 가능) |
| 💚 ADHD 친화 | 5~15분 단위 세분화, 격려 메시지, 부드러운 알림 |

## 빠른 시작 (10분 소요)

### 1단계: 텔레그램 봇 만들기 (2분)

1. 텔레그램에서 [@BotFather](https://t.me/BotFather)에게 메시지
2. `/newbot` 입력
3. 봇 이름 입력 (예: "내 업무비서")
4. 봇 username 입력 (예: "my_work_assistant_bot")
5. **토큰을 복사해두세요** (형식: `123456789:ABCdefGHIjklMNO...`)

### 2단계: Gemini API 키 발급 (2분)

1. [aistudio.google.com](https://aistudio.google.com/apikey) 접속
2. "Get API Key" → 새 키 생성
3. **키를 복사해두세요**

> 💡 **비용**: Gemini Flash 모델은 무료 티어가 있고, 유료도 매우 저렴합니다.
> Google One AI Premium 구독이 있으면 넉넉하게 사용 가능.

### 3단계: Railway로 배포 (5분)

1. [railway.app](https://railway.app) 가입 (GitHub 계정으로)
2. "New Project" → "Deploy from GitHub Repo" → 이 저장소 선택
3. Settings에서 Root Directory를 `assistant-bot`으로 설정
4. Variables 탭에서 환경변수 추가:

```
TELEGRAM_TOKEN=위에서_복사한_텔레그램_토큰
GEMINI_API_KEY=위에서_복사한_Gemini_API_키
```

5. Deploy 클릭!

> 💡 Railway 무료 플랜: 월 $5 크레딧 제공 (이 봇 운영에 충분)

### 4단계: Google 연동 (선택, 5분)

Google Calendar, Tasks, Sheets 연동을 원하시면:

1. [Google Cloud Console](https://console.cloud.google.com) 접속
2. 새 프로젝트 생성
3. APIs & Services → Library에서 활성화:
   - Google Calendar API
   - Google Tasks API
   - Google Sheets API
4. APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: Desktop app
   - Client ID와 Client Secret 복사
5. OAuth consent screen 설정 (외부, 테스트 사용자에 본인 이메일 추가)
6. Railway 환경변수에 추가:

```
GOOGLE_CLIENT_ID=복사한_Client_ID
GOOGLE_CLIENT_SECRET=복사한_Client_Secret
```

7. Google Sheets를 업무 로그로 쓰려면:
   - Google Sheets에서 새 스프레드시트 생성
   - URL에서 스프레드시트 ID 복사 (docs.google.com/spreadsheets/d/**여기**/edit)
   - 환경변수 추가:
   ```
   GOOGLE_SPREADSHEET_ID=복사한_스프레드시트_ID
   ```

8. 텔레그램 봇에서 `/google` 명령어로 계정 연결

## 사용법

### 기본 사용

그냥 자연어로 말하면 됩니다:

```
"다음 주 금요일까지 보고서 작성해야 해"
"오늘 저녁까지 이메일 답장 3개 보내기"
"이번 달 안에 포트폴리오 사이트 만들기"
```

AI가 자동으로:
- 태스크를 생성하고
- 데드라인을 설정하고
- 5~15분 단위의 작은 단계로 쪼개줍니다

### 명령어

| 명령어 | 설명 |
|--------|------|
| `/start` | 시작 & 안내 |
| `/tasks` | 전체 할 일 보기 |
| `/today` | 오늘 할 일 |
| `/done 번호` | 완료 처리 |
| `/progress 번호` | 진행 중 표시 |
| `/wbs 프로젝트설명` | WBS 자동 생성 |
| `/projects` | 프로젝트 목록 |
| `/stats` | 내 통계 |
| `/google` | Google 계정 연결 |
| `/help` | 도움말 |

### ADHD 친화 기능

- **작은 단위 세분화**: 모든 업무를 5~15분짜리 조각으로
- **"일단 5분만"**: 시작을 두려워하지 않도록 작은 시작 제안
- **축하 메시지**: 완료할 때마다 진심 어린 칭찬
- **부드러운 리마인더**: 재촉하지 않고 "혹시 이거 해볼까요?"
- **아침 브리핑**: 매일 아침 9시 오늘의 할 일 정리
- **가장 쉬운 것 먼저**: 항상 가장 작은 태스크부터 추천

## 로컬 개발

```bash
cd assistant-bot
pip install -r requirements.txt
cp .env.example .env
# .env 파일에 토큰 입력
python bot.py
```

## 아키텍처

```
텔레그램 앱 → Telegram Bot API → Python 서버
                                    ├── Gemini API (AI 두뇌)
                                    ├── SQLite (로컬 태스크 DB)
                                    ├── APScheduler (리마인더)
                                    └── Google APIs
                                         ├── Calendar (일정)
                                         ├── Tasks (할 일)
                                         └── Sheets (히스토리/업무일지)
```

## 월 비용 추정

| 항목 | 비용 |
|------|------|
| 텔레그램 | 무료 |
| Railway 서버 | ~$0 (무료 크레딧 $5/월) |
| Gemini API | 무료~$1/월 (Flash 무료 티어 있음, 구독 시 넉넉) |
| Google APIs | 무료 |
| **합계** | **월 $0~1** |
