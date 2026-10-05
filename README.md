# Reader

논문을 쉽게 읽도록 돕는 리더. 계획과 설계는 [docs/PLAN.md](docs/PLAN.md) 참고.

## 실행

```bash
# 백엔드 (http://localhost:8000) — 시작할 때 DB 마이그레이션이 자동 적용된다
cd backend
uv sync
uv run uvicorn app.main:app --reload

# 프론트엔드 (http://localhost:5173) — /api 요청은 백엔드로 프록시된다
cd frontend
npm install
npm run dev
```

백엔드를 다른 포트로 띄웠다면 프론트엔드 프록시 포트를 맞춘다: `API_PORT=8001 npm run dev`

## 테스트

```bash
cd backend && uv run pytest
cd frontend && npm test && npm run build && npm run lint
```

## 구조

```
backend/
  app/
    main.py            FastAPI 앱, 시작 시 Alembic 마이그레이션
    config.py          설정 (.env)
    models.py          Paper, Block
    storage.py         파일 저장소 인터페이스 (LocalStorage)
    parsing/           PDF → 블록·문장 파서 (PyMuPDF)
    text/              텍스트 정규화, 언어별 문장 분리
    importing/         주소·arXiv ID·DOI로 PDF와 메타데이터 가져오기 (안전한 fetch 포함)
    papers.py          논문 생성·파싱 결과 반영 (업로드·가져오기·재파싱 공용)
    routers/papers.py  업로드·가져오기·목록·파일·블록 API
    scripts/reparse.py 기존 논문 재파싱
  alembic/             DB 마이그레이션
  tests/
frontend/
  src/
    components/        Header, LeftSidebar, PdfViewer, SideInfo
    lib/               API 클라이언트, react-query 훅, 정규화, 드래그→블록·문장 매핑
    store.ts           Zustand 상태 (포커스 등)
shared/
  normalize_cases.json 프론트·백엔드 정규화 공통 테스트 케이스
```

## 파서를 바꾼 뒤

`backend/app/parsing/pymupdf_parser.py`의 `PARSER_VERSION`을 올리고 기존 논문을 다시 파싱한다.

```bash
cd backend && uv run python -m app.scripts.reparse
```

## DB 스키마 변경

```bash
cd backend
uv run alembic revision --autogenerate -m "설명"
uv run alembic upgrade head
```
