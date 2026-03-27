# Factory Dashboard V2

OpenClaw 에이전트의 API 비용, 토큰 사용량, 작업 큐를 실시간으로 모니터링하고 관리하는 대시보드.

> **Why?** AI 에이전트를 운영하면 토큰과 비용이 쌓입니다. Factory Dashboard는 어떤 에이전트가 어떤 모델에 얼마를 쓰는지 한눈에 보여주고, Task Queue로 작업을 자동 분배합니다.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Flask](https://img.shields.io/badge/flask-3.0-green)
![SQLite](https://img.shields.io/badge/sqlite-3-lightgrey)
![License](https://img.shields.io/badge/license-MIT-yellow)

<!-- 실제 대시보드 스크린샷을 캡처하면 아래 주석을 해제하세요 -->
<!-- ![Dashboard Screenshot](docs/screenshots/dashboard-overview.png) -->

---

## 목차

- [Quick Start](#quick-start)
- [주요 기능](#주요-기능)
- [아키텍처](#아키텍처)
- [대시보드 구성](#대시보드-구성)
- [Task Queue](#task-queue)
- [Auto-spawn 스케줄러](#auto-spawn-스케줄러)
- [안전장치](#안전장치)
- [설치 및 실행](#설치-및-실행)
- [설정](#설정)
- [API 엔드포인트](#api-엔드포인트)
- [프로젝트 구조](#프로젝트-구조)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [문서](#문서)
- [Contributing](#contributing)
- [License](#license)

---

## Quick Start

**5분 안에 시작하기:**

```bash
# 1. 클론 & 설치
git clone https://github.com/muin-company/factory-dashboard.git
cd factory-dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. 실행
python app.py

# 3. 브라우저에서 열기
open http://localhost:5051
```

> **전제 조건:** [OpenClaw](https://openclaw.com)가 설치되어 있고, `~/.openclaw/agents/` 에 세션 JSONL 파일이 존재해야 합니다. OpenClaw 에이전트가 한 번이라도 실행된 적 있으면 됩니다.

### 동작 확인

```bash
# 헬스체크
curl http://localhost:5051/api/health
# → {"status": "ok", "service": "factory-dashboard-v2"}

# 세션 데이터 조회
curl http://localhost:5051/api/sessions
# → JSON 응답 (에이전트별 비용/토큰 통계)

# Task Queue 조회
curl http://localhost:5051/api/tasks
# → 작업 목록 JSON
```

---

## 주요 기능

### 📊 비용 모니터링
- **실시간 비용 추적** — 에이전트별, 모델별 API 비용을 실시간 집계
- **구독 활용률** — Anthropic MAX, OpenAI Plus, Google AI Pro 등 구독 대비 실사용량 비교
- **일별 트렌드 차트** — 비용/토큰 사용량의 일별 추이를 stacked bar + cumulative line으로 시각화
- **에이전트 × 모델 매트릭스** — 어떤 에이전트가 어떤 모델을 얼마나 쓰는지 한눈에

### 📋 Task Queue (V2 신규)
- **작업 생성/관리** — Dashboard UI에서 작업을 생성하고 상태를 추적
- **우선순위 큐** — Priority 1(최고)~10(최저)로 작업 순서 관리
- **상태 추적** — pending → queued → running → done/failed 전체 라이프사이클

### 🤖 Auto-spawn (V2 신규)
- **자동 에이전트 할당** — 큐에 들어온 작업을 자동으로 서브에이전트에 분배
- **지능형 스케줄링** — 동시 실행 제한, 비용 한도, 타임아웃 자동 관리
- **모델 자동 선택** — 작업 유형에 따라 최적 모델 매핑

### 🔧 기타
- **활성 세션 모니터** — 현재 실행 중인 서브에이전트/cron 세션 상태
- **기간 필터** — 이번 주/이번 달/7d/14d/30d/전체 또는 커스텀 날짜 범위
- **자동 새로고침** — 30초마다 자동으로 데이터 갱신

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser (SPA)                        │
│                  Vanilla JS + Chart.js                       │
└──────────┬──────────────┬──────────────┬────────────────────┘
           │              │              │
     GET / (UI)    GET /api/*      POST /api/tasks
           │              │              │
┌──────────▼──────────────▼──────────────▼────────────────────┐
│                     Flask Server (app.py)                     │
│                      http://localhost:5051                    │
├─────────────────┬──────────────────┬────────────────────────┤
│  Cost Engine    │  Session Monitor │  Task Queue Manager     │
│  ┌───────────┐  │  ┌────────────┐  │  ┌──────────────────┐  │
│  │ JSONL     │  │  │ openclaw   │  │  │ SQLite DB        │  │
│  │ Parser    │  │  │ sessions   │  │  │ (data/factory.db)│  │
│  │ + Pricing │  │  │ --json     │  │  │                  │  │
│  └─────┬─────┘  │  └──────┬─────┘  │  └────────┬─────────┘  │
│        │        │         │        │           │            │
│        ▼        │         ▼        │           ▼            │
│  ~/.openclaw/   │   OpenClaw       │   TaskScheduler        │
│  agents/*/      │   Gateway        │   (scheduler.py)       │
│  sessions/      │                  │      │                 │
│  *.jsonl        │                  │      ▼                 │
│                 │                  │   openclaw agent       │
│                 │                  │   (서브에이전트 스폰)    │
└─────────────────┴──────────────────┴────────────────────────┘
```

### 데이터 흐름

1. **비용 데이터**: `~/.openclaw/agents/*/sessions/*.jsonl` → JSONL Parser → 모델별 가격 적용 → 집계
2. **세션 상태**: `openclaw sessions --json --active 120` → 실시간 세션 목록
3. **Task Queue**: 사용자 요청 → SQLite DB → Scheduler → `openclaw agent` 스폰
4. **설정**: `~/.openclaw/openclaw.json` → 에이전트 설정 읽기

### 기술 스택

| 컴포넌트 | 기술 |
|----------|------|
| 백엔드 | Flask (Python 3.10+) |
| 프론트엔드 | Vanilla JS SPA + Chart.js |
| 데이터베이스 | SQLite (Task Queue, WAL 모드) |
| 세션 데이터 | OpenClaw JSONL 트랜스크립트 (읽기 전용) |
| 실시간 업데이트 | 30초 폴링 (→ Phase 2에서 SSE 전환 예정) |

---

## 대시보드 구성

| 섹션 | 설명 |
|------|------|
| Summary Cards | 월 구독료, API 환산 가치, 총 토큰, 활성 일수 |
| Subscription Breakdown | 구독별 가격/사용량/절감액/활용률 |
| Utilization Bar | 전체 구독 대비 API 환산 가치 게이지 |
| **Task Queue** | 작업 목록 — 상태, 우선순위, 할당 에이전트 |
| Agent Breakdown | 에이전트별 비용/토큰/모델 요약 |
| Daily Charts (4종) | 비용 by Agent, 비용 by Model, 토큰 by Agent, 토큰 by Model |
| Model Usage Table | 모델별 상세 (비용, 토큰, 플랜, 사용 에이전트) |
| Agent × Model Matrix | 교차 비용 테이블 |
| Active Sessions | 실행 중인 세션 목록 |

<!-- 스크린샷이 준비되면 아래 주석을 해제하세요 -->
<!-- ### 스크린샷

| 화면 | 스크린샷 |
|------|----------|
| 메인 대시보드 | ![Overview](docs/screenshots/dashboard-overview.png) |
| Task Queue | ![Task Queue](docs/screenshots/task-queue.png) |
| 일별 차트 | ![Daily Charts](docs/screenshots/daily-charts.png) |
| 에이전트 매트릭스 | ![Agent Matrix](docs/screenshots/agent-matrix.png) |
| 설정 패널 | ![Settings](docs/screenshots/settings-panel.png) |
-->

---

## Task Queue

Task Queue는 Dashboard에서 직접 작업을 생성하고, 에이전트에 할당하여 실행 결과를 추적하는 시스템입니다.

### Task 생성

```bash
# API로 작업 생성
curl -X POST http://localhost:5051/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "블로그 SEO 분석",
    "description": "최근 30일간 발행된 블로그 포스트의 SEO 점수를 분석하고 개선점 제안",
    "type": "research",
    "priority": 3
  }'
```

또는 Dashboard UI의 **[+ New Task]** 버튼에서 모달로 생성할 수 있습니다.

### Task 상태 머신

```
                 ┌──────────┐
                 │  pending  │  ← 사용자가 생성
                 └────┬─────┘
                      │ enqueue()
                 ┌────▼─────┐
                 │  queued   │  ← 큐에 진입, 스폰 대기
                 └────┬─────┘
                      │ auto-spawn 또는 수동 실행
                 ┌────▼─────┐
    ┌───────────►│  running  │  ← 에이전트가 작업 중
    │            └──┬────┬───┘
    │               │    │
    │  retry    ┌───▼┐ ┌─▼────┐
    └───────────┤fail│ │ done │
                └────┘ └──────┘
                  │
                  ▼
              cancelled (수동 취소)
```

### Task 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | UUID | 작업 고유 식별자 |
| `title` | string | 작업 제목 (UI 표시용) |
| `description` | string | 상세 설명 / 에이전트에게 전달할 프롬프트 |
| `type` | enum | `general` \| `coding` \| `research` \| `content` |
| `priority` | int | 1(최고) ~ 10(최저), 기본값 5 |
| `status` | enum | `pending` \| `queued` \| `running` \| `done` \| `failed` \| `cancelled` |
| `agent_id` | string | 할당된 에이전트 (예: main, subagent:abc123) |
| `model` | string | 사용할 모델 (미지정 시 scheduler가 자동 선택) |
| `cost_usd` | float | 실행 비용 (완료 후 기록) |

### 데이터 저장소: SQLite

Task Queue는 **SQLite** (WAL 모드)를 사용합니다.

```
~/factory-dashboard-v2/data/
├── factory.db          # SQLite — task queue, 상태, 히스토리
└── queue/              # 대용량 payload 파일 (선택)
    └── task-abc123.json
```

**SQLite를 선택한 이유:**
- Python 표준 라이브러리 `sqlite3`로 즉시 사용 가능 (추가 설치 불필요)
- Task 상태 전이(`pending → running → done`)에 atomic update 적합
- 히스토리/통계 쿼리(일별 완료율, 평균 소요시간)에 SQL이 편리
- WAL 모드로 concurrent read/write 안전

---

## Auto-spawn 스케줄러

Auto-spawn은 큐에 들어온 작업을 자동으로 에이전트에 할당하고 실행하는 백그라운드 스케줄러입니다.

### 동작 방식

```
┌──────────┐     30초마다      ┌───────────────┐
│  Task    │ ──────────────► │  Scheduler    │
│  Queue   │   큐 체크        │  (_tick)       │
│ (SQLite) │                 │               │
└──────────┘                 └───────┬───────┘
                                     │
                          ┌──────────▼──────────┐
                          │  Safety Checks      │
                          │  1. 동시 실행 < 3?   │
                          │  2. 일일 비용 < $20? │
                          │  3. 모델 허용됨?     │
                          └──────────┬──────────┘
                                     │ (모두 통과)
                          ┌──────────▼──────────┐
                          │  openclaw agent     │
                          │  --prompt "..."     │
                          │  --model sonnet-4   │
                          │  서브에이전트 스폰    │
                          └─────────────────────┘
```

### 스케줄러 사이클 (매 30초)

1. **실행 중인 작업 수 확인** — `MAX_CONCURRENT` (기본 3) 이상이면 대기
2. **일일 비용 한도 체크** — `COST_LIMIT_DAILY` (기본 $20) 초과 시 스폰 중단
3. **우선순위 순으로 다음 작업 조회** — priority 낮은 숫자 우선, 같은 우선순위는 생성 시간 순
4. **에이전트 스폰** — `openclaw agent` CLI로 서브에이전트 생성
5. **세션 키 기록** — Task DB에 session_key 저장, 상태를 `running`으로 변경
6. **완료 감지** — 세션 종료 시 결과를 기록하고 상태를 `done`/`failed`로 업데이트

### 스폰 방식

**Phase 1 (현재): OpenClaw CLI 직접 호출**

```python
subprocess.Popen([
    'openclaw', 'agent',
    '--prompt', task.description,
    '--model', task.model or 'anthropic/claude-sonnet-4',
    '--json'
], stdout=log_file, stderr=log_file)
```

**Phase 2 (예정): Gateway ACP API 호출**

```python
resp = requests.post('http://localhost:19000/acp/sessions/spawn', json={
    'prompt': task.description,
    'model': task.model,
    'label': f'task-{task.id}',
})
session_key = resp.json()['sessionKey']
```

---

## 안전장치

Auto-spawn은 비용 폭주를 방지하기 위해 다중 안전장치를 갖추고 있습니다.

| 안전장치 | 설명 | 기본값 |
|----------|------|--------|
| **MAX_CONCURRENT** | 동시 실행 서브에이전트 수 제한 | `3` |
| **COST_LIMIT_DAILY** | 일일 자동 스폰 비용 상한 | `$20` |
| **COST_LIMIT_PER_TASK** | 단일 작업 비용 상한 | `$5` |
| **ALLOWED_MODELS** | 자동 스폰 허용 모델 화이트리스트 | sonnet, haiku, flash |
| **REQUIRE_APPROVAL** | 특정 타입 작업은 수동 승인 필요 | `coding` 타입 |
| **TIMEOUT_MINUTES** | 작업 최대 실행 시간 | `30분` |

### 비용 방어 레이어

```
Layer 1: 모델 화이트리스트
  └─ Opus 등 고비용 모델은 자동 스폰에서 제외
Layer 2: 작업별 비용 한도 ($5)
  └─ 단일 작업이 $5 초과 시 자동 중단
Layer 3: 일일 총 비용 한도 ($20)
  └─ 하루 전체 자동 스폰 비용이 $20 초과 시 큐 일시 정지
Layer 4: 동시 실행 제한 (3개)
  └─ 동시에 3개 이상 서브에이전트 스폰 불가
Layer 5: 타임아웃 (30분)
  └─ 30분 이상 실행 중인 작업은 자동 취소
```

### 비용이 높은 모델 사용 시

`claude-opus-4-6`이나 `gpt-4.1` 같은 고비용 모델은 기본적으로 자동 스폰 허용 목록에 포함되지 않습니다. 수동으로 실행하거나 설정에서 명시적으로 허용해야 합니다.

---

## 설치 및 실행

### 요구사항

- Python 3.10+
- [OpenClaw](https://openclaw.com) 설치 및 에이전트 실행 중
- `~/.openclaw/agents/` 에 세션 JSONL 파일 존재

### 설치

```bash
# 클론
git clone https://github.com/muin-company/factory-dashboard.git
cd factory-dashboard

# Python 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 실행

```bash
source venv/bin/activate
python app.py
# → http://localhost:5051
```

대시보드가 `http://localhost:5051`에서 열립니다. 브라우저에서 접속하면 바로 사용 가능합니다.

### 백그라운드 실행

```bash
# nohup으로 백그라운드 실행
nohup python app.py > logs/dashboard.log 2>&1 &

# 또는 systemd 서비스로 등록 (Linux)
# sudo cp factory-dashboard.service /etc/systemd/system/
# sudo systemctl enable factory-dashboard
# sudo systemctl start factory-dashboard
```

---

## 설정

### 기본 설정 (app.py)

`app.py` 상단에서 조정 가능:

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `PRICING` | 모델별 API 가격 (input/output/cacheRead/cacheWrite per 1M tokens) | 내장 가격표 |
| `SUBSCRIPTION_PRICING` | 구독 서비스별 월 요금 | Anthropic MAX $200, OpenAI Plus $20, Google AI Pro $19.99 |
| `OPENCLAW_BASE` | OpenClaw agents 디렉토리 경로 | `~/.openclaw/agents` |
| `OPENCLAW_CONFIG` | OpenClaw 설정 파일 경로 | `~/.openclaw/openclaw.json` |

### 스케줄러 설정 (config.json)

`data/config.json`으로 스케줄러 동작을 제어합니다:

```json
{
  "scheduler": {
    "enabled": true,
    "max_concurrent": 3,
    "poll_interval_seconds": 30,
    "cost_limit_daily_usd": 20.0,
    "cost_limit_per_task_usd": 5.0,
    "timeout_minutes": 30,
    "allowed_models": [
      "claude-sonnet-4",
      "claude-haiku-3.5",
      "gemini-2.5-flash",
      "gemini-3-flash"
    ],
    "require_approval_types": ["coding"],
    "model_mapping": {
      "general": "claude-sonnet-4",
      "coding": "claude-sonnet-4",
      "research": "gemini-2.5-flash",
      "content": "claude-haiku-3.5"
    }
  },
  "dashboard": {
    "refresh_interval_seconds": 30,
    "default_date_range": "this_month",
    "timezone": "Asia/Seoul"
  }
}
```

### 설정 API

스케줄러 설정은 API로도 조회/변경할 수 있습니다:

```bash
# 현재 설정 조회
curl http://localhost:5051/api/scheduler/config

# 설정 변경
curl -X PATCH http://localhost:5051/api/scheduler/config \
  -H "Content-Type: application/json" \
  -d '{"max_concurrent": 5, "cost_limit_daily_usd": 30.0}'
```

---

## 데이터 소스

`~/.openclaw/agents/{agent}/sessions/*.jsonl` 파일에서 직접 파싱합니다.
각 assistant 메시지의 `usage` 필드에서 토큰 수와 비용을 추출하고,
`app.py` 내장 가격표(`PRICING`)로 실제 API 비용을 계산합니다.

### 지원 모델

| 제공자 | 모델 | 비용 유형 |
|--------|------|-----------|
| Anthropic | Claude Opus 4, Sonnet 4, Haiku 3.5 | 구독 (MAX) |
| OpenAI | GPT-4o, GPT-4.1, GPT-5.3 Codex | 구독 (Plus) |
| Google | Gemini 2.5/3 Pro, Gemini 2.5/3 Flash | 구독 (AI Pro) / 종량제 |
| xAI | Grok 2, Grok 4 | 종량제 |

새 모델 추가 시 `app.py`의 `PRICING` 딕셔너리에 항목을 추가하면 됩니다.

---

## API 엔드포인트

### 비용 모니터링

#### `GET /`

대시보드 UI를 서빙합니다.

#### `GET /api/sessions`

세션 정보 + 누적 통계를 JSON으로 반환합니다.

**Query Parameters:**

| 파라미터 | 타입 | 설명 | 예시 |
|----------|------|------|------|
| `from` | `string` | 시작 날짜 (YYYY-MM-DD) | `2026-03-01` |
| `to` | `string` | 종료 날짜 (YYYY-MM-DD) | `2026-03-20` |

<details>
<summary>응답 예시 (클릭하여 펼치기)</summary>

```json
{
  "success": true,
  "sessions": {
    "main": {
      "id": "main",
      "key": "agent:main:main",
      "model": "claude-opus-4-6",
      "status": "active",
      "tokensIn": 123456,
      "tokensOut": 7890,
      "cost": 1.23
    },
    "subagents": [
      {
        "id": "abc123",
        "key": "agent:main:subagent:abc123",
        "model": "claude-sonnet-4",
        "status": "active",
        "tokensIn": 50000,
        "tokensOut": 3000,
        "cost": 0.45
      }
    ],
    "cron": []
  },
  "stats": {
    "total": 5,
    "subagents": 3,
    "cron": 1,
    "activeSubagents": 2
  },
  "cumulative": {
    "totalCost": 145.67,
    "dailyCost": 4.85,
    "monthlyCost": 145.50,
    "subscriptionTotal": 239.99,
    "utilization": 250.5,
    "totalTokens": 50000000,
    "byAgent": { "...": "에이전트별 비용/토큰" },
    "byModel": { "...": "모델별 비용/토큰" },
    "dailyCostByAgent": [],
    "dailyCostByModel": [],
    "agentModelMatrix": {}
  }
}
```

</details>

#### `GET /api/health`

헬스체크 엔드포인트.

```json
{"status": "ok", "service": "factory-dashboard-v2"}
```

### Task Queue API

#### `POST /api/tasks` — 작업 생성

```bash
curl -X POST http://localhost:5051/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "README 번역",
    "description": "README.md를 영문으로 번역",
    "type": "content",
    "priority": 5,
    "model": "claude-sonnet-4"
  }'
```

#### `GET /api/tasks` — 작업 목록

```bash
# 전체 목록
curl http://localhost:5051/api/tasks

# 상태 필터
curl "http://localhost:5051/api/tasks?status=running"

# 에이전트 필터
curl "http://localhost:5051/api/tasks?agent_id=main"
```

#### `GET /api/tasks/:id` — 작업 상세

#### `PATCH /api/tasks/:id` — 상태/우선순위 변경

```bash
curl -X PATCH http://localhost:5051/api/tasks/abc123 \
  -H "Content-Type: application/json" \
  -d '{"priority": 1, "status": "queued"}'
```

#### `POST /api/tasks/:id/run` — 수동 실행

```bash
curl -X POST http://localhost:5051/api/tasks/abc123/run
```

#### `POST /api/tasks/:id/cancel` — 실행 중 작업 취소

#### `DELETE /api/tasks/:id` — 작업 삭제

#### `GET /api/tasks/stats` — 큐 통계

```json
{
  "pending": 3,
  "queued": 2,
  "running": 1,
  "done_today": 12,
  "failed_today": 1,
  "total_cost_today": 8.45
}
```

---

## 프로젝트 구조

```
factory-dashboard-v2/
├── app.py                  # Flask 서버 + JSONL 파싱 + 비용 계산 + Task API
├── db.py                   # SQLite DB 관리 (Task CRUD, 마이그레이션)
├── scheduler.py            # Auto-spawn 스케줄러 (백그라운드 데몬 스레드)
├── requirements.txt        # Python 의존성 (Flask, Flask-CORS)
├── .gitignore
├── README.md
├── CONTRIBUTING.md         # 기여 가이드
├── USER_GUIDE.md           # 사용자 가이드
├── LICENSE                 # MIT License
├── data/
│   ├── factory.db          # SQLite — Task Queue DB
│   └── queue/              # 대용량 payload 파일 (선택)
├── migrations/             # DB 스키마 마이그레이션
├── logs/                   # 로그 파일
└── static/
    ├── index.html          # 대시보드 HTML (SPA)
    ├── js/
    │   └── dashboard.js    # Chart.js 기반 차트 렌더링 + 데이터 바인딩
    └── css/
        └── dashboard.css   # 반응형 스타일 (모바일 대응)
```

---

## Troubleshooting

### 서버가 시작되지 않을 때

**증상:** `python app.py` 실행 시 에러 발생

```bash
# 1. Python 버전 확인 (3.10+ 필요)
python3 --version

# 2. 가상환경 활성화 확인
which python  # → .../factory-dashboard-v2/venv/bin/python 이어야 함

# 3. 의존성 재설치
pip install -r requirements.txt

# 4. 포트 충돌 확인
lsof -i :5051
# 다른 프로세스가 사용 중이면 종료하거나 app.py에서 포트 변경
```

### 데이터가 표시되지 않을 때

**증상:** 대시보드에 "No data" 또는 빈 차트

```bash
# 1. OpenClaw 세션 파일 존재 확인
ls ~/.openclaw/agents/*/sessions/*.jsonl

# 2. JSONL 파일이 비어있지 않은지 확인
wc -l ~/.openclaw/agents/*/sessions/*.jsonl

# 3. OpenClaw 에이전트가 실행 중인지 확인
openclaw sessions --json --active 120

# 4. API 직접 호출하여 데이터 확인
curl http://localhost:5051/api/sessions | python3 -m json.tool
```

### Task Queue가 동작하지 않을 때

**증상:** 작업을 생성해도 실행되지 않음

```bash
# 1. SQLite DB 파일 확인
ls -la data/factory.db

# 2. 스케줄러 상태 확인
curl http://localhost:5051/api/scheduler/config
# → "enabled": true 인지 확인

# 3. 동시 실행 한도 확인
curl http://localhost:5051/api/tasks?status=running
# → MAX_CONCURRENT(3) 이상이면 대기 중

# 4. 일일 비용 한도 확인
curl http://localhost:5051/api/tasks/stats
# → total_cost_today가 $20 이상이면 스폰 중단됨

# 5. OpenClaw Gateway 상태 확인
openclaw gateway status
# → Gateway가 실행 중이어야 에이전트 스폰 가능
```

### 비용이 이상하게 높을 때

```bash
# 1. 어떤 에이전트가 비용을 많이 쓰는지 확인
curl "http://localhost:5051/api/sessions" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for agent, info in data['cumulative']['byAgent'].items():
    print(f'{agent}: \${info[\"cost\"]:.2f}')
"

# 2. 구독 vs 종량제 비용 분리 확인
# Dashboard UI의 Subscription Breakdown 섹션 확인

# 3. 비용 한도 조정
curl -X PATCH http://localhost:5051/api/scheduler/config \
  -H "Content-Type: application/json" \
  -d '{"cost_limit_daily_usd": 10.0}'
```

### 흔한 에러 메시지

| 에러 | 원인 | 해결 |
|------|------|------|
| `SQLITE_BUSY` | DB 동시 쓰기 충돌 | 자동 재시도됨 (정상) |
| `FileNotFoundError: openclaw.json` | OpenClaw 설정 파일 없음 | OpenClaw 설치 확인 |
| `Connection refused :5051` | Flask 서버 미실행 | `python app.py` 실행 |
| `No JSONL files found` | 세션 데이터 없음 | OpenClaw 에이전트 실행 필요 |
| `Gateway not running` | OpenClaw Gateway 다운 | `openclaw gateway start` |

---

## Roadmap

### ✅ Phase 1: 비용 모니터링 (완료)

- [x] JSONL 트랜스크립트 파싱 엔진
- [x] 모델별 API 가격 계산
- [x] 구독 활용률 분석 (Anthropic MAX, OpenAI Plus, Google AI Pro)
- [x] 에이전트별/모델별 비용 집계
- [x] 일별 트렌드 차트 (Chart.js)
- [x] 에이전트 × 모델 교차 매트릭스
- [x] 활성 세션 모니터
- [x] 기간 필터 (커스텀 날짜 범위)
- [x] 반응형 UI (모바일 대응)
- [x] 자동 새로고침 (30초)

### 🔄 Phase 2: Task Queue + Auto-spawn (진행 중)

- [x] SQLite 기반 Task Queue DB
- [x] Task CRUD API
- [x] Task 상태 머신 (pending → queued → running → done/failed)
- [x] Auto-spawn 스케줄러 (백그라운드 데몬)
- [x] 안전장치 (동시 실행 제한, 비용 한도, 타임아웃)
- [ ] Task Queue UI (리스트 뷰, 생성 모달, 상세 뷰)
- [ ] 스케줄러 설정 패널 (UI)
- [ ] 실시간 작업 로그 스트리밍
- [ ] Task 완료/실패 알림

### 📋 Phase 3: 고급 기능 (계획)

- [ ] **비용 추적 고도화** — 작업별 정확한 비용 귀속, 일별/주별/월별 비용 리포트
- [ ] **자동 재시도** — 실패 시 최대 2회 재시도 (다른 모델로 폴백)
- [ ] **동적 우선순위** — 대기 시간에 따라 우선순위 자동 상승 (priority aging)
- [ ] **Task 의존성** — Task B는 Task A 완료 후 실행
- [ ] **반복 작업** — 매일/매주 반복 실행 (cron-like)
- [ ] **SSE 실시간 업데이트** — 폴링 → Server-Sent Events 전환
- [ ] **알림 연동** — Telegram/Discord/Slack 작업 완료 알림
- [ ] **CSV/JSON 데이터 내보내기**
- [ ] **다크모드**
- [ ] **Docker 이미지** — `docker run` 한 줄로 실행
- [ ] **다중 호스트 지원** — 원격 에이전트 모니터링
- [ ] **Gateway ACP 연동** — CLI → API 전환으로 안정성 향상

---

## 문서

| 문서 | 설명 |
|------|------|
| [README.md](README.md) | 이 문서 — 프로젝트 개요, 아키텍처, API 레퍼런스 |
| [USER_GUIDE.md](USER_GUIDE.md) | 사용자 가이드 — 실행, 화면 구성, 지표 해석, 문제 해결 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 기여 가이드 — 개발 환경, 모델 추가, PR 규칙 |

---

## Contributing

기여를 환영합니다! 자세한 내용은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.

### 빠른 시작

```bash
# 개발 환경 설정
git clone https://github.com/muin-company/factory-dashboard.git
cd factory-dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 개발 서버 실행
python app.py
# → http://localhost:5051

# 변경 후 테스트
curl http://localhost:5051/api/health        # 서버 동작 확인
curl http://localhost:5051/api/sessions      # 데이터 확인
curl http://localhost:5051/api/tasks         # Task Queue 확인
```

### 커밋 컨벤션

```
feat: 새 기능 추가
fix: 버그 수정
docs: 문서 수정
style: UI/CSS 변경
refactor: 코드 리팩토링
```

### 자주 하는 기여

- **새 모델 가격 추가**: `app.py`의 `PRICING` 딕셔너리에 항목 추가
- **구독 서비스 추가**: `SUBSCRIPTION_PRICING` + `classify_model()` 업데이트
- **새 차트 추가**: `static/index.html`에 `<canvas>` + `dashboard.js`에 렌더링 로직

---

## License

MIT — 자유롭게 사용하고 수정하세요. [LICENSE](LICENSE) 파일을 참고하세요.
