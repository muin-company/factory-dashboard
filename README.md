# Factory Dashboard V2

OpenClaw 에이전트의 API 비용 및 토큰 사용량을 실시간으로 모니터링하는 대시보드.

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

```bash
# 클론
git clone https://github.com/muin-company/factory-dashboard.git
cd factory-dashboard

# Python 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 실행
python app.py
# → http://localhost:5051
```

## 요구사항

- Python 3.10+
- [OpenClaw](https://openclaw.com) 설치 및 에이전트 실행 중
- `~/.openclaw/agents/` 에 세션 JSONL 파일 존재

## 데이터 소스

`~/.openclaw/agents/{agent}/sessions/*.jsonl` 파일에서 직접 파싱합니다.
각 assistant 메시지의 `usage` 필드에서 토큰 수와 비용을 추출하고,
`app.py` 내장 가격표(`PRICING`)로 실제 API 비용을 계산합니다.

## 설정

`app.py` 상단에서 조정 가능:

- `PRICING` — 모델별 API 가격 (input/output/cacheRead/cacheWrite per 1M tokens)
- `SUBSCRIPTION_PRICING` — 구독 서비스별 월 요금
- `OPENCLAW_BASE` — OpenClaw agents 디렉토리 경로

## 프로젝트 구조

```
app.py                  Flask 서버 + JSONL 파싱 + 비용 계산 엔진
static/
  index.html            대시보드 HTML (SPA)
  js/dashboard.js       Chart.js 기반 차트 렌더링 + 데이터 바인딩
  css/dashboard.css     반응형 스타일 (모바일 대응)
requirements.txt        Python 의존성 (Flask, Flask-CORS)
```

## API

| Endpoint | Method | 설명 |
|----------|--------|------|
| `/` | GET | 대시보드 UI |
| `/api/sessions?from=YYYY-MM-DD&to=YYYY-MM-DD` | GET | 세션 + 누적 통계 JSON |
| `/api/health` | GET | 헬스체크 |

## License

MIT
