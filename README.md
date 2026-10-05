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

## 테스트

```bash
cd backend && uv run pytest
cd frontend && npm run build && npm run lint
```

## 구조

```
backend/
  app/
    main.py            FastAPI 앱, 시작 시 Alembic 마이그레이션
    config.py          설정 (.env)
    models.py          Paper, Block
    storage.py         파일 저장소 인터페이스 (LocalStorage)
    parsing/           PDF → 블록 파서 (PyMuPDF)
    routers/papers.py  업로드·목록·파일·블록 API
  alembic/             DB 마이그레이션
  tests/
frontend/
  src/
    components/        Header, LeftSidebar, PdfViewer, SideInfo
    lib/               API 클라이언트, react-query 훅, 선택→블록 매핑
    store.ts           Zustand 상태
```

## DB 스키마 변경

```bash
cd backend
uv run alembic revision --autogenerate -m "설명"
uv run alembic upgrade head
```
