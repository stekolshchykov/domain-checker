# Domain Checker API

HTTP API-сервис для проверки доступности доменов через Namecheap. Работает внутри Docker-контейнера с headless Firefox (Playwright).

## Стек

- **Python 3.12 + FastAPI**
- **Playwright (headless Firefox)**
- **Docker + Docker Compose**
- **pytest** для тестирования

## Быстрый старт

```bash
docker-compose up --build api
```

API будет доступен по адресу `http://localhost:8000`.

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

## API Endpoints

### `POST /check`

Принимает массив доменов и возвращает их статус. Ограничений на количество доменов нет — запрос выполняется до конца.

**Request:**
```json
{
  "domains": ["google.com", "knowflow.com"]
}
```

**Response 200 OK:**
```json
{
  "results": [
    {
      "domain": "google.com",
      "status": "taken",
      "price": null,
      "currency": null,
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
  "checked_at": "2026-04-16T11:31:30Z",
  "total_checks": 2
}
```

#### Возможные статусы домена

| Статус | Описание | Пример цены |
|--------|----------|-------------|
| `available` | Домен свободен для регистрации | `€9.33/yr` |
| `taken` | Домен уже зарегистрирован | `null` |
| `premium` | Домен доступен, но премиальный | `€8,842.53` |
| `unknown` | Не удалось определить статус | `null` |

#### Примеры ответов для разных сценариев

**Свободный домен:**
```json
{
  "domain": "qwertyuiop12345abc.com",
  "status": "available",
  "price": "€9.33/yr",
  "currency": "EUR",
  "source": "namecheap_page"
}
```

**Занятый домен:**
```json
{
  "domain": "google.com",
  "status": "taken",
  "price": null,
  "currency": null,
  "source": "namecheap_page"
}
```

**Несуществующий TLD (валидный формат):**
```json
{
  "domain": "nonexistent-tld-12345.zzz",
  "status": "available",
  "price": null,
  "currency": null,
  "source": "aftermarket_api"
}
```

### `GET /health`

Health check с проверкой готовности браузера.

**Response 200 OK:**
```json
{
  "status": "ok",
  "browser_ready": true,
  "timestamp": "2026-04-16T11:30:17Z"
}
```

## HTTP коды ответов

| Код | Сценарий |
|-----|----------|
| `200 OK` | Успешная проверка доменов или health check |
| `400 Bad Request` | Невалидный JSON или отсутствует обязательное поле |
| `422 Unprocessable Entity` | Ошибка валидации: пустой список, невалидный формат домена |
| `429 Too Many Requests` | Rate limit превышен (редко, т.к. есть внутренний throttle) |
| `500 Internal Server Error` | Непредвиденная ошибка |
| `503 Service Unavailable` | Браузер не готов к работе |

## Валидация доменов

API проверяет формат каждого домена **до** открытия браузера. Следующие значения отклоняются с `422`:

- `not_a_domain` — отсутствует точка
- `domain with spaces` — содержит пробелы
- `test.` — заканчивается точкой
- `-example.com` — начинается с дефиса
- `example-.com` — дефис перед точкой
- `[]` / `null` — пустой список или не строка

Если формат валиден, но TLD не существует, API вернёт `available` на основе Aftermarket API Namecheap.

## Особенности работы

- **Rate limiting:** между любыми двумя проверками доменов строгий интервал **5 секунд**. Например, 10 доменов займут минимум **45 секунд**.
- **Page reuse:** несколько доменов в одном запросе проверяются последовательно в **одной вкладке Firefox** без пересоздания.
- **Fallback:** если страница Namecheap недоступна или не содержит данных, используется Aftermarket API.
- **Без таймаута соединения:** сервер не разрывает HTTP-соединение, сколько бы ни длилась проверка.

## Тестирование (только в Docker)

```bash
docker-compose --profile test run --rm test
```

На текущий момент реализовано **16 тестов**, включая:
- проверку занятых, свободных и premium-доменов
- валидацию пустых и невалидных доменов
- проверку rate-limiting (≥5 сек между доменами)
- проверку reuse page

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `PLAYWRIGHT_HEADLESS` | Headless-режим браузера | `true` |
| `RATE_LIMIT_SECONDS` | Минимальный интервал между проверками | `5.0` |
| `PAGE_TIMEOUT_MS` | Таймаут загрузки одной страницы | `15000` |
| `LONG_HEALTH_CHECK_DOMAIN` | Длинный домен для тестов | `this-is-very-long-health-check-domain-name-test-1234567890.com` |
