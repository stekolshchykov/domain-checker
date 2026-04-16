# PRD: Domain Checker API

## 1. Общее описание проекта

**Domain Checker** — это HTTP API-сервис, развёртываемый в Docker-контейнере. Он принимает один или несколько доменных имён и возвращает их статус доступности для регистрации, а также цену (если домен свободен) или информацию о занятости (если домен уже зарегистрирован).

Данные собираются **в реальном времени** из открытого интерфейса регистратора Namecheap через автоматизацию браузера (Playwright) и вспомогательные внутренние API Namecheap.

---

## 2. Цели и задачи

| # | Задача | Критерий успеха |
|---|---|---|
| 1 | Принимать запросы с одним или множеством доменов | `POST /check` поддерживает массив `domains` любого размера |
| 2 | Определять статус домена | `available` / `taken` / `premium` / `unknown` |
| 3 | Извлекать цену регистрации | Для свободных/Premium доменов возвращать `price` и `currency` |
| 4 | Работать через реальный браузер в фоне | Playwright headless Chromium внутри Docker |
| 5 | Реализовать корректное API-поведение | HTTP-коды, валидация, структурированные ошибки |
| 6 | Развёртываться и тестироваться в Docker | `docker-compose up --build` + `docker-compose run --rm test` |
| 7 | Покрыть тестами разные сценарии | ≥10 автоматизированных API-тестов на занятые и свободные домены |

---

## 3. Исследование Namecheap

### 3.1. Страница результатов
URL шаблон:
```
https://www.namecheap.com/domains/registration/results/?domain=<DOMAIN>
```

Примеры:
- `https://www.namecheap.com/domains/registration/results/?domain=KnowFlow.com`
- `https://www.namecheap.com/domains/registration/results/?domain=qwertyuiop12345abc.com`

### 3.2. Варианты ответа на странице

При анализе DOM-структуры загруженной страницы выявлены следующие паттерны:

#### A. Занятый домен (Taken)
- Присутствует текстовая метка: `Taken` или `Registered in YYYY`
- Кнопка действия: `Make offer`
- Пример доменов: `knowflow.xyz`, `knowflow.io`, `knowflow.cloud`

#### B. Свободный домен (Available)
- Отображается цена регистрации (например: `€9.33/yr`, `€4.23/yr`)
- Кнопка действия: `Add to cart`
- Может присутствовать скидочный бейдж: `42% OFF`, `New`
- Пример доменов: `qwertyuiop12345abc.com`, `qwertyuiop12345abc.org`

#### C. Премиум-домен (Premium)
- Метка: `Premium`
- Высокая цена (например: `€8,842.53`)
- Кнопка: `Add to cart`
- Пример: `knowflow.com` (premium)

### 3.3. Внутренние API Namecheap

В процессе загрузки страницы Namecheap выполняет XHR-запросы. Некоторые из них можно использовать как дополнительный источник данных:

**Aftermarket Status API:**
```
GET https://aftermarket.namecheapapi.com/domain/status?domain=<DOMAIN>
```

Ответы:
- Свободен: `{"type":"ok","data":[{"domain":"qwertyuiop12345abc.com","status":"notfound"}]}`
- Занят/Aftermarket: `{"type":"ok","data":[{"domain":"knowflow.com","status":"active","price":10405,"retail":10456,"type":"buynow","username":"sedo"}]}`

> **Примечание:** этот API возвращает информацию только о доменах, находящихся в aftermarket-списке, или `notfound`. Для полного анализа (скидки, точные розничные цены, премиум-статус) требуется парсинг основной страницы через браузер.

---

## 4. Технологический стек

| Компонент | Технология | Обоснование |
|---|---|---|
| **Backend** | Python 3.12 + FastAPI | Простота, скорость разработки, встроенная валидация (Pydantic), async из коробки |
| **Browser Automation** | Playwright (async API) | Официальная поддержка headless Chromium, стабильная работа в Docker, удобный Python API |
| **Server** | Uvicorn | Стандартный ASGI-сервер для FastAPI, работает в Docker без проблем |
| **Тестирование** | pytest + pytest-asyncio + HTTPX | HTTPX — родной async клиент для тестирования FastAPI, pytest-asyncio для Playwright-фикстур |
| **Конфигурация** | Pydantic Settings + `.env` | Типобезопасная конфигурация, удобно в Docker через `environment:` |
| **Контейнеризация** | Docker + Docker Compose | Один `docker-compose.yml` для подъёма сервиса и запуска тестов |

### Почему Python + FastAPI + Playwright в Docker — оптимальный выбор
- **Playwright** имеет официальные Docker-образы (`mcr.microsoft.com/playwright/python:v1.x.x-jammy`) с предустановленными системными зависимостями и браузерами.
- **FastAPI** + **Uvicorn** легко упаковываются в один контейнер, быстро стартуют и потребляют минимум ресурсов.
- Не требуется отдельный Selenium Grid или сложная оркестрация — всё работает в **одном контейнере**.
- Для тестов достаточно `docker-compose run --rm test`, который запустит браузер внутри того же образа.

---

## 5. Архитектура решения

### 5.1. Диаграмма

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Container                         │
│  ┌─────────────────┐      POST /check       ┌───────────┐  │
│  │   Клиент        │ ─────────────────────> │  FastAPI  │  │
│  │   (curl/tests)  │  { "domains": [...] }  │   App     │  │
│  └─────────────────┘                        └─────┬─────┘  │
│                                                   │         │
│                                                   ▼         │
│                                         ┌───────────────┐  │
│                                         │ RateLimited   │  │
│                                         │ Namecheap     │  │
│                                         │ Scraper       │  │
│                                         │ (Playwright)  │  │
│                                         └───────┬───────┘  │
│                                                 │          │
│                                                 ▼          │
│                                         ┌───────────────┐  │
│                                         │  Headless     │  │
│                                         │  Chromium     │  │
│                                         └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 5.2. Алгоритм проверки одного домена

1. **Запуск браузера** (если ещё не запущен) — Playwright Chromium в headless-режиме.
2. **Открытие страницы** `https://www.namecheap.com/domains/registration/results/?domain=<domain>`.
3. **Ожидание загрузки** результатов (до 10 секунд).
4. **Закрытие cookie-диалога** (если появился).
5. **Парсинг DOM:**
   - Ищем заголовок с точным именем домена (например, `h2: "knowflow.com"`).
   - Определяем наличие меток: `Taken`, `Registered in`, `Premium`.
   - Определяем тип кнопки: `Make offer` (занят) или `Add to cart` (свободен/премиум).
   - Извлекаем цену из элемента `strong` рядом с доменом.
6. **Fallback на Aftermarket API:** если DOM не содержит чёткого результата (например, таймаут или капча), делаем запрос к `aftermarket.namecheapapi.com`.
7. **Формирование результата:**
   - `status`: `available` | `taken` | `premium` | `unknown`
   - `price`: строка с ценой или `null`
   - `currency`: извлечённая валюта (`EUR`, `USD`) или `null`
   - `source`: `namecheap_page` | `aftermarket_api` | `unknown`

### 5.3. Обработка нескольких доменов и Rate Limiting

#### A. Переиспользование вкладки (page reuse)
- Если в одном API-запросе передано **несколько доменов**, они проверяются **последовательно в одной и той же вкладке** браузера.
- После проверки первого домена страница **не закрывается**. Вместо этого выполняется навигация (`page.goto()`) к URL следующего домена.
- Это снижает накладные расходы на создание/закрытие контекстов и уменьшает цифровой след для анти-фрода Namecheap.

#### B. Жёсткий rate limit — минимум 5 секунд между любыми запросами
- Между **любыми двумя последовательными проверками доменов** (в рамках одного API-запроса или между разными API-запросами) должен соблюдаться интервал **не менее 5 секунд**.
- Для реализации используется глобальный асинхронный семафор + трекер времени последнего запроса (`last_request_at`).
- Перед каждым `page.goto()` скрапер вычисляет: `sleep = max(0, 5.0 - (now - last_request_at))` и обязательно делает `await asyncio.sleep(sleep)`.
- Таким образом, даже если клиент передал 100 доменов в одном `POST /check`, они будут обрабатываться в одной вкладке с паузой ≥5 секунд между каждым. Сервер не разрывает соединение — запрос дожидается финала проверки последнего домена.

#### C. Параллелизм
- Параллельная обработка разных API-запросов допускается, но каждая проверка домена всё равно проходит через общий rate-limiter.
- Максимальное количество одновременных проверок (семафор) ограничено **1** для гарантии соблюдения 5-секундного интервала между любыми парами запросов.
- При необходимости масштабирования в будущем можно добавить пул вкладок с индивидуальными rate-limiter’ами, но на старте — **1 page, 1 контекст, 5 секунд delay**.

---

## 6. API Спецификация

### 6.1. Проверка доменов

**Endpoint:** `POST /check`

**Request Body:**
```json
{
  "domains": ["example.com", "brand-new-startup.io", "knowflow.com"]
}
```

> **Примечание:** ограничений на количество доменов в одном запросе нет. Сервер не разрывает HTTP-соединение по таймауту — запрос выполняется до тех пор, пока не будут проверены все домены.

**Response 200 OK:**
```json
{
  "results": [
    {
      "domain": "example.com",
      "status": "taken",
      "price": null,
      "currency": null,
      "source": "namecheap_page"
    },
    {
      "domain": "brand-new-startup.io",
      "status": "available",
      "price": "€29.73/yr",
      "currency": "EUR",
      "source": "namecheap_page"
    },
    {
      "domain": "knowflow.com",
      "status": "premium",
      "price": "€8,842.53",
      "currency": "EUR",
      "source": "namecheap_page"
    }
  ],
  "checked_at": "2026-04-16T10:35:00Z",
  "total_checks": 3
}
```

**Status enum:**
- `available` — домен свободен для регистрации, есть цена.
- `taken` — домен уже зарегистрирован.
- `premium` — домен доступен, но относится к премиум-категории с повышенной ценой.
- `unknown` — не удалось определить статус (ошибка, капча, таймаут).

### 6.2. Health Check

**Endpoint:** `GET /health`

**Response 200 OK:**
```json
{
  "status": "ok",
  "browser_ready": true,
  "timestamp": "2026-04-16T10:35:00Z"
}
```

### 6.3. Модель внутреннего rate-limiter

В `scraper.py` реализован класс `RateLimitedScraper` с атрибутами:
- `_last_request_at: float` — timestamp последнего HTTP-запроса к Namecheap.
- `_lock: asyncio.Lock` — гарантирует, что только один домен проверяется в данный момент.

Псевдокод метода `_throttle()`:
```python
async def _throttle(self):
    async with self._lock:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < 5.0:
            await asyncio.sleep(5.0 - elapsed)
        self._last_request_at = time.monotonic()
```

Метод `check_domains(domains: list[str])`:
1. Открывает одну `page` (если ещё не открыта).
2. Для каждого домена вызывает `_throttle()`.
3. Выполняет `await page.goto(url)`.
4. Парсит DOM.
5. После обработки всех доменов **не закрывает** `page` — оставляет её открытой для следующего API-запроса (или закрывает при shutdown приложения).

### 6.4. Коды ответов и обработка ошибок

| HTTP Code | Сценарий | Тело ответа |
|-----------|----------|-------------|
| `200 OK` | Успешная проверка доменов | `{ "results": [...], "checked_at": "...", "total_checks": N }` |
| `201 Created` | — (резерв) | — |
| `400 Bad Request` | Невалидный JSON, отсутствует обязательное поле | `{ "detail": "Invalid JSON body" }` или Pydantic validation error |
| `422 Unprocessable Entity` | Ошибка валидации Pydantic (пустой список, невалидный домен, >N доменов) | Стандартный Pydantic error response |
| `429 Too Many Requests` | Глобальный rate limiter API-уровня (если клиенты шлют слишком много запросов) | `{ "detail": "Rate limit exceeded. Try again later." }` |
| `500 Internal Server Error` | Непредвиденная ошибка скрапера, браузер упал | `{ "detail": "Internal server error" }` |
| `503 Service Unavailable` | Браузер не готов, невозможно установить соединение с Namecheap | `{ "detail": "Browser not ready" }` или `{ "detail": "Namecheap unavailable" }` |

#### Структура ошибок (Unified Error Model)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      { "field": "domains", "message": "List must contain at least 1 domain" }
    ]
  }
}
```

#### Кастомные Exception Handler’ы FastAPI
- `ValidationError` → 422 с unified error model
- `DomainCheckError` (кастомное исключение скрапера) → 503 или 500
- `RateLimitExceeded` → 429
- `Exception` (catch-all) → 500 с минимальной информацией (production-safe)

---

## 7. Docker-инфраструктура

### 7.1. Dockerfile

Используется официальный образ Playwright как базовый для избежания ручной установки системных зависимостей Chromium.

```dockerfile
# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.51.0-noble

WORKDIR /app

# Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# App code
COPY src/ ./src/
COPY tests/ ./tests/

ENV PYTHONUNBUFFERED=1
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 7.2. Docker Compose

```yaml
version: "3.9"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - PLAYWRIGHT_HEADLESS=true
      - RATE_LIMIT_SECONDS=5.0
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

  test:
    build: .
    environment:
      - APP_ENV=test
      - PLAYWRIGHT_HEADLESS=true
      - RATE_LIMIT_SECONDS=5.0
      - TEST_BASE_URL=http://api:8000
    command: ["pytest", "-v", "tests/"]
    depends_on:
      api:
        condition: service_healthy
    profiles:
      - test
```

### 7.3. Команды для локальной разработки и тестирования

```bash
# Поднять сервис
docker-compose up --build api

# Запустить тесты внутри Docker (только в Docker!)
docker-compose --profile test run --rm test

# Остановить всё
docker-compose down
```

### 7.4. Почему тесты обязаны запускаться именно в Docker
- Официальный образ Playwright содержит все системные библиотеки, необходимые для headless Chromium (libnss3, libatk, libcups и т.д.).
- Эти зависимости сложно поддерживать в едином виде на разных хостовых ОС (macOS, разные дистрибутивы Linux).
- Docker гарантирует **воспроизводимость** тестов: один и тот же браузер, одинаковые шрифты, одинаковое окружение.
- `docker-compose --profile test run --rm test` — единственный supported способ локального прогона тестов.

---

## 8. Этапы реализации

### Этап 1 — Подготовка окружения
- [ ] Инициализация Python-проекта (`pyproject.toml`)
- [ ] Установка зависимостей: `fastapi`, `uvicorn[standard]`, `playwright`, `pydantic-settings`, `httpx`, `pytest`, `pytest-asyncio`, `pytest-playwright`
- [ ] Создание `Dockerfile` на базе `mcr.microsoft.com/playwright/python:v1.51.0-noble`
- [ ] Создание `docker-compose.yml` с сервисами `api` и `test`
- [ ] Проверка подъёма контейнера: `docker-compose up --build api`

### Этап 2 — Разработка модуля браузер-скрапинга
- [ ] Создание `src/scraper.py` с классом `RateLimitedScraper`
- [ ] Реализация `_throttle()` с 5-секундной задержкой и `asyncio.Lock`
- [ ] Реализация `check_domain(domain: str) -> DomainResult` с headless Chromium
- [ ] Настройка User-Agent и viewport для снижения риска блокировки
- [ ] Реализация парсинга DOM по селекторам страницы Namecheap
- [ ] Интеграция fallback на Aftermarket API
- [ ] Обработка ошибок (таймаут, неожиданная структура страницы)

### Этап 3 — Разработка API
- [ ] Создание `src/main.py` с FastAPI приложением
- [ ] Реализация Pydantic-моделей (`src/models.py`) для запросов/ответов/ошибок
- [ ] Реализация эндпоинтов `POST /check` и `GET /health`
- [ ] Реализация кастомных exception handler’ов (422, 429, 500, 503)
- [ ] Глобальный lifecycle управление browser-контекстом (startup / shutdown)

### Этап 4 — Интеграция Docker и локальное тестирование
- [ ] Настройка `Dockerfile` для копирования `src/` и `tests/`
- [ ] Успешный запуск сервиса через `docker-compose up --build api`
- [ ] Проверка endpoint’ов из хоста: `curl http://localhost:8000/health`

### Этап 5 — Тестирование (только в Docker)
- [ ] Написание API-тестов в `tests/test_api.py`
- [ ] Тесты должны покрывать:
  - Свободные домены (минимум 5)
  - Занятые домены (минимум 5)
  - Премиум-домен (минимум 1)
  - Проверку ошибок валидации (пустой список, невалидный домен)
  - **Rate-limiting:** замер времени между проверками в одном запросе (≥5 сек)
  - **Reuse page:** проверка что при множественных доменах в одном запросе не создаётся больше 1 page
- [ ] Успешный прогон: `docker-compose --profile test run --rm test`

### Этап 6 — Документирование
- [ ] README.md с инструкциями по запуску в Docker
- [ ] Примеры запросов через `curl`
- [ ] Описание переменных окружения

---

## 9. Тест-план (≥10 тестов)

| # | Тест | Ожидаемый результат | Тип домена / сценарий |
|---|------|---------------------|----------------------|
| 1 | `POST /check` → `["google.com"]` | `status: taken` | Занятый |
| 2 | `POST /check` → `["facebook.com"]` | `status: taken` | Занятый |
| 3 | `POST /check` → `["amazon.com"]` | `status: taken` | Занятый |
| 4 | `POST /check` → `["knowflow.com"]` | `status: premium`, `price` присутствует | Премиум |
| 5 | `POST /check` → `["knowflow.xyz"]` | `status: taken` | Занятый |
| 6 | `POST /check` → `["qwertyuiop12345abc.com"]` | `status: available`, `price` присутствует | Свободный |
| 7 | `POST /check` → `["brandnewstartup-test-2026.org"]` | `status: available`, `price` присутствует | Свободный |
| 8 | `POST /check` → `["super-random-domain-999.net"]` | `status: available`, `price` присутствует | Свободный |
| 9 | `POST /check` → `["google.com", "qwertyuiop12345abc.com"]` | Оба результата корректны | Микс |
| 10 | `POST /check` → `[]` | HTTP 422 Validation Error | Ошибка валидации |
| 11 | `GET /health` | `status: ok`, `browser_ready: true` | Health check |
| 12 | `POST /check` → 3 домена | Общее время ≥10 сек (2 интервала по 5 сек) | Rate limit |
| 13 | `POST /check` → 2 домена, затем `POST /check` → 1 домен | Между запросами ≥5 сек, создано не более 1 page | Rate limit + reuse page |

> **Важно:** во время выполнения тестов Playwright обязан запускать браузер в фоновом режиме (headless) **внутри Docker-контейнера**.

---

## 10. Структура проекта

```
domain-checker/
├── PRD.md                      # <- настоящий документ
├── README.md                   # Инструкции по запуску в Docker
├── Dockerfile                  # Образ на базе Playwright Python
├── docker-compose.yml          # Сервисы api + test
├── pyproject.toml              # Зависимости Python
├── .env.example                # Пример переменных окружения
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI приложение + exception handlers
│   ├── config.py               # Pydantic Settings
│   ├── scraper.py              # Playwright-скрапер Namecheap
│   ├── models.py               # Pydantic модели API
│   └── exceptions.py           # Кастомные исключения
└── tests/
    ├── __init__.py
    ├── conftest.py             # Фикстуры pytest (event_loop, http_client)
    └── test_api.py             # API-тесты (запускаются в Docker)
```

---

## 11. Требования к окружению

- Docker Engine 24.0+ и Docker Compose v2+
- ~2 GB свободного места на диске (образ Playwright + Chromium)
- Доступ в интернет для загрузки страниц Namecheap
- Порт `8000` свободен на хосте (или настраивается через `.env`)

---

## 12. Ограничения и риски

| Риск | Митигация |
|------|-----------|
| Namecheap может изменить DOM страницы | Мониторинг через тесты CI + fallback на Aftermarket API |
| Rate limiting / капча | 1 page + 5-секундная задержка между любыми запросами, headless-режим с реальным User-Agent |
| Медленная загрузка страницы | Таймаут 10–15 секунд, graceful degradation до `unknown` |
| Зависимость от внешнего сайта | Логирование ошибок, retry-механизм |
| Playwright в Docker требует много места | Использование официального slim-образа, регулярная очистка неиспользуемых слоёв |

---

## 13. Дальнейшее развитие (roadmap)

- [ ] Поддержка bulk-проверки через внутренний API Namecheap Beast Mode
- [ ] Кэширование результатов в Redis (TTL 1 час)
- [ ] Webhook-уведомления об изменении статуса домена
- [ ] Поддержка других регистраторов (GoDaddy, Porkbun)
- [ ] Масштабирование через пул browser-контекстов (при сохранении rate-limit’ов)

---

*Документ составлен: 2026-04-16*
*Автор: AI Agent (Kimi CLI)*
