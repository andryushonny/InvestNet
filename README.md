# InvestNet

Personal AI-инструмент инвестиционного нетворкинга. Локальное Windows-приложение:
импортирует Gmail / LinkedIn-архивы, строит профили контактов, ранжирует их
под ваш инвест-кейс, генерирует персонализированные холодные письма и ведёт
встроенный CRM.

Подробное ТЗ — `docs/SPEC.md`.

## Самый простой способ — собрать в GitHub Actions

На вашем компьютере **ничего не нужно** ставить, даже Python и Node.

1. Запушьте этот репозиторий в свой GitHub.
2. Откройте вкладку **Actions** → выберите workflow **«Build Windows portable»** → **Run workflow**.
3. Через 5–10 минут заберите артефакт `InvestNet-portable` (это `.zip`) — это и есть готовое портативное приложение.
4. Если создадите git-тег вида `v1.0.0`, артефакты автоматически прицепятся к GitHub Release.

## Требования (если собираете локально на Windows)

- Windows 10/11 x64
- Python 3.11 (https://www.python.org/downloads/release/python-3119/) — поставить с галочкой "Add to PATH"
- Node.js 20 LTS (https://nodejs.org/) — поставить с галочкой "Add to PATH"
- ~6 ГБ свободного диска на время сборки

## Сборка одной командой

Из корня репозитория в **PowerShell** или **cmd**:

```bat
scripts\build.bat
```

После завершения готовый портативный дистрибутив лежит в `bin\InvestNet\`.
Архив для переноса на другие машины: `bin\InvestNet-portable.zip`.

На целевых машинах **не нужны** ни Python, ни Node.js — просто разархивировать
и запустить `InvestNet.exe`.

## Структура репозитория

```
backend/      Python FastAPI backend (упаковывается PyInstaller-ом)
frontend/     Electron + React + Vite (упаковывается electron-builder-ом)
scripts/      Скрипты сборки (build.bat, dev.bat)
docs/         Документация и ТЗ
bin/          (gitignored) Артефакты сборки
```

## Разработка (с установленными Python/Node)

```bat
scripts\dev.bat
```

Запустит backend в режиме hot-reload (uvicorn) и Vite dev-сервер с Electron.

## Конфигурация

При первом запуске откроется онбординг. Введите API-ключ OpenRouter
(https://openrouter.ai/keys) или OpenAI. Все данные хранятся локально в
`%APPDATA%\InvestNet\`.
