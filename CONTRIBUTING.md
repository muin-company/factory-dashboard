# Contributing

Factory Dashboard에 기여해주셔서 감사합니다! 🎉

## 개발 환경 설정

```bash
git clone https://github.com/muin-company/factory-dashboard.git
cd factory-dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## 프로젝트 구조

- `app.py` — Flask 서버, JSONL 파싱, 비용 계산 (백엔드 전체)
- `static/index.html` — 대시보드 HTML
- `static/js/dashboard.js` — Chart.js 차트 + 데이터 바인딩
- `static/css/dashboard.css` — 스타일시트

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

- **백엔드** (`app.py`): 새 모델 가격 추가, API 엔드포인트 확장, 파싱 로직 수정
- **프론트엔드** (`static/`): 차트 추가, UI 개선, 반응형 레이아웃

### 4. 커밋 & PR

```bash
git add .
git commit -m "feat: 기능 설명"
git push origin feat/기능명
```

GitHub에서 Pull Request를 생성하세요.

## 커밋 컨벤션

```
feat: 새 기능 추가
fix: 버그 수정
docs: 문서 수정
style: UI/CSS 변경
refactor: 코드 리팩토링
```

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

## 코드 스타일

- Python: 표준 PEP 8
- JavaScript: 세미콜론 사용, camelCase
- HTML/CSS: 기존 스타일 따르기

## 라이선스

MIT — 자유롭게 사용하고 수정하세요.
