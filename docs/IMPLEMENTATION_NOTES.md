# Implementation notes

## Что реализовано в коде

| Модуль | Статус | Где |
|---|---|---|
| FastAPI backend, SQLite, миграции через `SQLModel.metadata.create_all` | ✅ | `backend/app/main.py`, `backend/app/db/` |
| LLM Gateway (OpenAI + OpenRouter, единый интерфейс) | ✅ | `backend/app/llm/gateway.py` |
| Gmail mbox-импортер (streaming, фильтры, дедуп, talon-очистка) | ✅ | `backend/app/importers/gmail.py` |
| LinkedIn ZIP-импортер (Connections + messages) | ✅ | `backend/app/importers/linkedin.py` |
| Indexer + FAISS HNSW + sqlite-map (две коллекции) | ✅ | `backend/app/indexing/` |
| Enricher (ddgs web search + httpx + LLM JSON) | ✅ | `backend/app/enrichment/` |
| Ranker (двухэтапный retrieval + LLM-score) | ✅ | `backend/app/ranking/ranker.py` |
| Email composer | ✅ | `backend/app/composer/composer.py` |
| REST API + SSE для прогресса задач | ✅ | `backend/app/api/routes.py`, `tasks.py` |
| Electron + React UI: Onboarding, Dashboard, Contacts, Person card, Cases, Pipeline (kanban DnD), Email composer, Settings, Tasks | ✅ | `frontend/` |
| PyInstaller-сборка backend.exe (onedir) | ✅ | `backend/backend.spec`, `scripts/build.bat` |
| electron-builder: portable + NSIS | ✅ | `frontend/package.json` |
| Один скрипт сборки `scripts\build.bat` → `bin\InvestNet\` | ✅ | `scripts/build.bat` |

## Сознательные упрощения (vs. ТЗ)

- **Talon**: используется при наличии в окружении; если упаковка под Windows
  капризничает, чистка падает на regex-fallback (`importers/cleaner.py`). MVP-приемлемо.
- **Пред-фильтрация в FAISS**: использован post-filter (берём `top_k * 5`),
  как описано в ТЗ §7.5.
- **Embedding dimensions = 512** для `text-embedding-3-small` (Matryoshka),
  снижает размер индекса вдвое относительно полного 1536-d.
- **PyInstaller onedir, не onefile**: onefile разворачивает архив в `%TEMP%`
  при каждом запуске (~7–15 сек запуска, плохой UX). onedir даёт `<5 сек`
  старт согласно НФТ. Размер бандла тот же.
- **Drag-and-drop канбана** реализован на нативном HTML5 DnD без `dnd-kit`,
  чтобы сэкономить ~100 КБ бандла и зависимостей.
- **Не упакован shadcn/ui** — компонентов всего ~7, написаны на Tailwind напрямую.
- **Code-signing** не настроен (MVP). См. ТЗ §17.

## Известные ограничения первой итерации

- Backend single-process; долгие импорты выполняются в `asyncio.to_thread`,
  что хватает для одного пользователя.
- `vector_store` сохраняется на shutdown и явно после каждого `index_*`;
  при kill-9 индекс может отстать от sqlite-map (восстановится переиндексацией
  через Settings → «Перестроить индекс»).
- Web search через `ddgs` может вернуть пусто на нестабильной сети — enricher
  graceful-fallback на «только переписка».

## Как добавить mac/linux сборки (out of MVP)

```bash
cd frontend && npx electron-builder --mac --linux
# плюс PyInstaller на соответствующей ОС — кросс-сборку он не делает.
```
