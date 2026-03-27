# Contributing

Factory Dashboard에 기여해주셔서 감사합니다! 🎉

## 개발 환경 설정

### 요구사항

- Python 3.10+
- Git
- [OpenClaw](https://openclaw.com) (선택 — 없어도 UI 개발 가능)

### 설치

```bash
# 1. 레포 클론
git clone https://github.com/muin-company/factory-dashboard.git
cd factory-dashboard

# 2. Python 가상환경 생성 & 활성화
python3 -m venv venv
source venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 개발 서버 실행
python app.py
# → http://localhost:5051
```

### 프로젝트 구조

```
factory-dashboard-v2/
├── app.py                  # Flask 서버 + JSONL 파싱 + 비용 계산 + Task API
├── db.py                   # SQLite DB 관리 (Task CRUD, 마이그레이션)
├── scheduler.py            # Auto-spawn 스케줄러 (백그라운드 데몬)
├── requirements.txt        # Python 의존성
├── data/
│   └── factory.db          # SQLite DB (Task Queue)
├── migrations/             # DB 스키마 마이그레이션
├── static/
│   ├── index.html          # 대시보드 HTML (SPA)
│   ├── js/dashboard.js     # Chart.js 차트 + 데이터 바인딩
│   └── css/dashboard.css   # 반응형 스타일
├── README.md
├── USER_GUIDE.md
└── CONTRIBUTING.md         # 이 파일
```

---

## 테스트

현재 자동화된 테스트 스위트는 없습니다. 변경 후 다음을 확인하세요:

### 필수 확인 항목

```bash
# 1. 서버 시작 — 에러 없이 시작되는지
python app.py

# 2. 헬스체크
curl http://localhost:5051/api/health
# → {"status": "ok", "service": "factory-dashboard-v2"}

# 3. 세션 API 응답
curl http://localhost:5051/api/sessions
# → 유효한 JSON 반환

# 4. Task API 응답
curl http://localhost:5051/api/tasks
# → 유효한 JSON 반환

# 5. UI 확인 (브라우저)
# - 차트가 정상 렌더링되는지
# - 기간 필터가 동작하는지
# - 모바일 뷰에서 레이아웃이 깨지지 않는지
```

### Task Queue 테스트

```bash
# Task 생성
curl -X POST http://localhost:5051/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Test task", "description": "Testing", "priority": 5}'

# Task 목록 조회
curl http://localhost:5051/api/tasks

# Task 상태 변경
curl -X PATCH http://localhost:5051/api/tasks/<TASK_ID> \
  -H "Content-Type: application/json" \
  -d '{"status": "queued"}'

# Task 삭제
curl -X DELETE http://localhost:5051/api/tasks/<TASK_ID>
```

---

## 기여 방법

### 1. Issue 확인

작업 전에 [Issues](https://github.com/muin-company/factory-dashboard/issues)에서 관련 이슈가 있는지 확인하세요.

### 2. 브랜치 생성

```bash
git checkout -b feat/기능명
# 또는
git checkout -b fix/버그명
```

### 3. 변경 사항 작성

- **백엔드** (`app.py`, `db.py`, `scheduler.py`): API, 파싱, 스케줄러 로직
- **프론트엔드** (`static/`): 차트, UI 컴포넌트, 스타일
- **문서** (`*.md`): README, 사용자 가이드, 기여 가이드

### 4. 커밋 & PR

```bash
git add .
git commit -m "feat: 기능 설명"
git push origin feat/기능명
```

GitHub에서 Pull Request를 생성하세요.

---

## 커밋 컨벤션

```
feat: 새 기능 추가
fix: 버그 수정
docs: 문서 수정
style: UI/CSS 변경
refactor: 코드 리팩토링
perf: 성능 개선
test: 테스트 추가/수정
chore: 빌드/설정 변경
```

---

## 자주 하는 기여

### 새 모델 가격 추가

`app.py`의 `PRICING` 딕셔너리에 항목을 추가합니다:

```python
PRICING = {
    # ...
    'new-model-name': {'input': 1.0, 'output': 5.0, 'cacheRead': 0.1},
}
```

가격 단위는 **1M 토큰당 USD**입니다. [LiteLLM 가격표](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json)를 참고하세요.

### 구독 서비스 추가

`SUBSCRIPTION_PRICING`에 항목을 추가하고, `classify_model()` 함수에서 분류 로직을 업데이트합니다.

### 새 차트 추가

1. `static/index.html`에 `<canvas>` 요소 추가
2. `static/js/dashboard.js`에서 Chart.js로 차트 렌더링

---

## PR 가이드라인

### PR 제출 전 체크리스트

- [ ] 서버가 에러 없이 시작됨
- [ ] 기존 API 엔드포인트가 정상 동작함
- [ ] UI가 데스크톱/모바일에서 깨지지 않음
- [ ] 커밋 메시지가 컨벤션을 따름
- [ ] 새 기능이면 README에 설명 추가
- [ ] 새 API 엔드포인트면 사용 예시 포함

### PR 설명 템플릿

```markdown
## 변경 사항
- 무엇을 변경했는지 간략히 설명

## 테스트
- 어떻게 테스트했는지

## 스크린샷 (UI 변경 시)
- Before / After 스크린샷 첨부
```

---

## 코드 스타일

- **Python**: PEP 8 표준
- **JavaScript**: 세미콜론 사용, camelCase
- **HTML/CSS**: 기존 스타일 따르기
- **커밋 메시지**: 한국어 또는 영어, 동사로 시작

---

## 로드맵 / 기여 아이디어

현재 기여를 환영하는 영역:

- [ ] Task Queue UI 개선 (리스트 뷰, 필터, 정렬)
- [ ] 다크모드 지원
- [ ] 단위 테스트 추가 (pytest)
- [ ] Docker 이미지 제공
- [ ] CSV/JSON 데이터 내보내기
- [ ] 알림 기능 (Telegram/Discord 연동)
- [ ] 다중 호스트 지원 (원격 에이전트 모니터링)

---

## 라이선스

MIT — 자유롭게 사용하고 수정하세요.
