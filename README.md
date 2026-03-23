# Factory Dashboard V2

OpenClaw 에이전트의 API 비용 및 토큰 사용량을 실시간으로 모니터링하는 대시보드.

> **Why?** AI 에이전트를 운영하면 토큰과 비용이 쌓입니다. Factory Dashboard는 어떤 에이전트가 어떤 모델에 얼마를 쓰는지 한눈에 보여줍니다.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Flask](https://img.shields.io/badge/flask-3.0-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

## 주요 기능

- **실시간 비용 추적** — 에이전트별, 모델별 API 비용을 실시간 집계
- **구독 활용률** — Anthropic MAX, OpenAI Plus, Google AI Pro 등 구독 대비 실사용량 비교
- **일별 트렌드 차트** — 비용/토큰 사용량의 일별 추이를 stacked bar + cumulative line으로 시각화
- **에이전트 × 모델 매트릭스** — 어떤 에이전트가 어떤 모델을 얼마나 쓰는지 한눈에
- **활성 세션 모니터** — 현재 실행 중인 서브에이전트/cron 세션 상태
- **기간 필터** — 이번 주/이번 달/7d/14d/30d/전체 또는 커스텀 날짜 범위
- **자동 새로고침** — 30초마다 자동으로 데이터 갱신

## 대시보드 구성

| 섹션 | 설명 |
|------|------|
| Summary Cards | 월 구독료, API 환산 가치, 총 토큰, 활성 일수 |
| Subscription Breakdown | 구독별 가격/사용량/절감액/활용률 |
| Utilization Bar | 전체 구독 대비 API 환산 가치 게이지 |
| Agent Breakdown | 에이전트별 비용/토큰/모델 요약 |
| Daily Charts (4종) | 비용 by Agent, 비용 by Model, 토큰 by Agent, 토큰 by Model |
| Model Usage Table | 모델별 상세 (비용, 토큰, 플랜, 사용 에이전트) |
| Agent × Model Matrix | 교차 비용 테이블 |
| Active Sessions | 실행 중인 세션 목록 |

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

## 설정

`app.py` 상단에서 조정 가능:

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `PRICING` | 모델별 API 가격 (input/output/cacheRead/cacheWrite per 1M tokens) | 내장 가격표 |
| `SUBSCRIPTION_PRICING` | 구독 서비스별 월 요금 | Anthropic MAX $200, OpenAI Plus $20, Google AI Pro $19.99 |
| `OPENCLAW_BASE` | OpenClaw agents 디렉토리 경로 | `~/.openclaw/agents` |
| `OPENCLAW_CONFIG` | OpenClaw 설정 파일 경로 | `~/.openclaw/openclaw.json` |

## 프로젝트 구조

```
factory-dashboard/
├── app.py                  # Flask 서버 + JSONL 파싱 + 비용 계산 엔진
├── requirements.txt        # Python 의존성 (Flask, Flask-CORS)
├── .gitignore
├── README.md
├── CONTRIBUTING.md
└── static/
    ├── index.html          # 대시보드 HTML (SPA)
    ├── js/
    │   └── dashboard.js    # Chart.js 기반 차트 렌더링 + 데이터 바인딩
    └── css/
        └── dashboard.css   # 반응형 스타일 (모바일 대응)
```

## API 엔드포인트

### `GET /`

대시보드 UI를 서빙합니다.

### `GET /api/sessions`

세션 정보 + 누적 통계를 JSON으로 반환합니다.

**Query Parameters:**

| 파라미터 | 타입 | 설명 | 예시 |
|----------|------|------|------|
| `from` | `string` | 시작 날짜 (YYYY-MM-DD) | `2026-03-01` |
| `to` | `string` | 종료 날짜 (YYYY-MM-DD) | `2026-03-20` |

**Response:**

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
    "daysRunning": 30,
    "activeDays": 25,
    "subscriptionTotal": 239.99,
    "subscriptionBreakdown": {
      "anthropic_max": {
        "price": 200.0,
        "estimatedApiCost": 580.50,
        "savings": 380.50,
        "utilization": 290.3
      }
    },
    "utilization": 250.5,
    "totalEstimatedApiCost": 601.23,
    "payperUseCost": 12.34,
    "totalTokens": 50000000,
    "totalInput": 40000000,
    "totalOutput": 8000000,
    "totalCacheRead": 2000000,
    "totalCacheWrite": 500000,
    "byAgent": {
      "MJ": {
        "cost": 120.50,
        "tokens": 40000000,
        "input": 30000000,
        "output": 8000000,
        "cacheRead": 2000000,
        "cacheWrite": 500000,
        "model": "claude-opus-4-6"
      }
    },
    "byModel": {},
    "dailyCostByAgent": [
      {"date": "2026-03-01", "MJ": 5.23, "bori": 1.02}
    ],
    "dailyCostByModel": [],
    "dailyTokensByAgent": [],
    "dailyTokensByModel": [],
    "agentModelMatrix": {
      "MJ": {"claude-opus-4-6": 100.50, "claude-sonnet-4": 20.00}
    },
    "dateRange": {
      "start": "2026-03-01T00:00:00+00:00",
      "end": "2026-03-20T23:59:59+00:00"
    }
  }
}
```

### `GET /api/health`

헬스체크 엔드포인트.

**Response:**

```json
{
  "status": "ok",
  "service": "factory-dashboard-v2"
}
```

## 아키텍처

```
Browser (SPA)
    │
    ├── GET /              → static/index.html
    ├── GET /api/sessions  → Flask → parse JSONL files + openclaw CLI
    └── GET /api/health    → Flask → health status
         │
         ├── ~/.openclaw/agents/*/sessions/*.jsonl  (토큰/비용 데이터)
         └── ~/.openclaw/openclaw.json              (에이전트 설정)
```

- **프론트엔드**: Vanilla JS SPA, [Chart.js](https://www.chartjs.org/) 차트 렌더링
- **백엔드**: Flask (Python), 30초마다 클라이언트가 API 폴링
- **데이터**: OpenClaw 세션 JSONL 파일을 직접 파싱 (별도 DB 없음)

## 문서

| 문서 | 설명 |
|------|------|
| [USER_GUIDE.md](USER_GUIDE.md) | 사용자 가이드 — 실행, 화면 구성, 지표 해석, 문제 해결 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 기여 가이드 — 개발 환경, 모델 추가, PR 규칙 |
| [README.md](README.md) | 이 문서 — 프로젝트 개요 및 API 레퍼런스 |

## License

MIT
