# Atoma — Beautician Booking API

A production-style backend for booking beauticians, built with FastAPI,
PostgreSQL, Redis, and SQLAlchemy. Features JWT authentication, role-based
access control (RBAC), a 5-state booking state machine, and Redis distributed
locking to prevent double-booking under concurrent load.

[![Tests](https://img.shields.io/badge/tests-23%20passing-brightgreen)](#testing)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688)](https://fastapi.tiangolo.com/)

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Domain Model](#domain-model)
- [Setup](#setup)
- [Running the API](#running-the-api)
- [Testing](#testing)
- [API Reference](#api-reference)
- [Design Decisions](#design-decisions)
- [Known Limitations](#known-limitations)
- [Future Improvements](#future-improvements)

---

## Features

- **JWT authentication** with bcrypt password hashing
- **Role-based access control** — `user`, `beautician`, `admin`
- **5-state booking state machine** with strict transition validation
- **Redis distributed locking** to prevent double-booking race conditions
- **PostgreSQL** with Alembic migrations for schema versioning
- **23 automated tests** covering auth, RBAC, state machine, concurrency, and services
- **Async-safe booking** — concurrent requests for the same beautician are serialized

---

## Architecture

```
┌────────────────┐
│    Client      │
└───────┬────────┘
        │ HTTP + JWT
        ▼
┌────────────────────┐      ┌─────────────────┐
│   FastAPI (app)    │─────▶│   PostgreSQL    │
│  - Auth (JWT)      │      │  - users        │
│  - RBAC            │      │  - beauticians  │
│  - Booking API     │      │  - services     │
│  - State machine   │      │  - bookings     │
└─────────┬──────────┘      └─────────────────┘
          │
          │ SET NX EX 60
          ▼
   ┌─────────────┐
   │    Redis    │
   │ (lock keys) │
   └─────────────┘
```

### Request Flow for Booking Creation

1. Client `POST /booking` with `beautician_id` and optional `service_id`
2. FastAPI validates JWT, checks role = `user`
3. Service layer looks up the beautician
4. Redis lock acquired: `SET lock:beautician:{id} <uuid> NX EX 60`
5. Beautician marked unavailable, booking created with status `Requested`
6. Lock released (only if still held by this request)
7. Response returned to client

Under concurrent load, only one request can hold the lock for a given
beautician. Others either retry with a different beautician (auto-assign
case) or return 404.

---

## Domain Model

### User Roles

| Role | Can do |
|---|---|
| `user` (customer) | Create bookings, view own bookings, list beauticians |
| `beautician` | Manage own availability, accept bookings, view assigned bookings |
| `admin` | View all users/bookings/beauticians, create services |

### Booking State Machine

```
          ┌─────────────┐
          │  Requested  │
          └──────┬──────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
   ┌──────────┐     ┌───────────┐
   │ Accepted │     │ Cancelled │  (terminal)
   └────┬─────┘     └───────────┘
        │
        ├──────▶ ┌───────────┐
        │        │ Cancelled │  (terminal)
        │        └───────────┘
        ▼
   ┌─────────────┐
   │ In Progress │
   └──────┬──────┘
          ▼
     ┌───────────┐
     │ Completed │  (terminal)
     └───────────┘
```

Valid transitions:

| From | To |
|---|---|
| Requested | Accepted, Cancelled |
| Accepted | In Progress, Cancelled |
| In Progress | Completed |
| Completed | (none — terminal) |
| Cancelled | (none — terminal) |

Invalid transitions are rejected with `403 Forbidden`.

When a booking reaches `Completed` or `Cancelled`, the beautician is
automatically marked available again.

---

## Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 14+
- Redis 5+

### Install

```bash
git clone https://github.com/codingbetas/beautician-booking.git
cd beautician-booking

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

### Configure

Copy `.env.example` to `.env` and fill in your credentials:

```bash
copy .env.example .env
```

Edit `.env`:

```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/atoma_dev
TEST_DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/atoma_test
SECRET_KEY=change-me-to-a-long-random-string
REDIS_URL=redis://localhost:6379/0
```

### Create the databases

```bash
psql -U postgres -c "CREATE DATABASE atoma_dev;"
psql -U postgres -c "CREATE DATABASE atoma_test;"
```

### Apply migrations

```bash
alembic upgrade head
```

### Seed sample data (optional)

```bash
python seed.py
```

---

## Running the API

Two processes need to run simultaneously:

**Terminal 1 — Redis:**

```bash
redis-server.exe        # Windows
# redis-server          # Mac/Linux
```

**Terminal 2 — FastAPI:**

```bash
uvicorn app.main:app --reload
```

API: `http://127.0.0.1:8000`
Swagger docs: `http://127.0.0.1:8000/docs`

---

## Testing

Install test dependencies:

```bash
pip install -r requirements-dev.txt
```

Ensure Redis is running (locking tests need it). Ensure `atoma_test`
exists (see Setup).

Run the full suite:

```bash
pytest tests/ -v
```

Expected:

```
======================== 23 passed in ~11s =========================
```

### Test coverage

| File | Tests | What it verifies |
|---|---|---|
| `test_auth.py` | 7 | Signup, login, JWT requirement, duplicate email, admin-role rejection |
| `test_rbac.py` | 5 | Customers can't accept bookings; beauticians can't create them; admin-only routes |
| `test_state_machine.py` | 5 | Valid transitions succeed, invalid rejected, terminal states locked |
| `test_locking.py` | 2 | **Concurrent bookings for the same beautician — only one succeeds** |
| `test_services.py` | 4 | Active-only filtering, auth required, admin-only creation |

The concurrency test is the most important: it spawns two simultaneous
booking requests for the same beautician and asserts exactly one
succeeds and one fails.

---

## API Reference

### Auth

| Method | Endpoint | Body | Auth |
|---|---|---|---|
| POST | `/signup` | `{name, email, password, role, location}` | None |
| POST | `/login` | form-urlencoded `username, password` | None |
| GET | `/me` | — | Bearer |

### Beauticians

| Method | Endpoint | Body/Params | Auth |
|---|---|---|---|
| POST | `/beautician` | `{name, location}` | Beautician |
| GET | `/beauticians` | — | User / Admin |
| PUT | `/beautician/availability` | `?available=true` | Beautician |

### Bookings

| Method | Endpoint | Body/Params | Auth |
|---|---|---|---|
| POST | `/booking` | `{beautician_id?, service_id?}` | User |
| GET | `/bookings` | `?status_filter=Requested` | Any |
| PUT | `/booking/{id}/status` | `?new_status=In Progress` | Beautician / Admin |
| PUT | `/booking/{id}/accept` | — | Beautician |

### Admin

| Method | Endpoint | Auth |
|---|---|---|
| GET | `/admin/users` | Admin |
| GET | `/admin/beauticians` | Admin |
| GET | `/admin/bookings` | Admin |
| POST | `/admin/services` | Admin |

### Services

| Method | Endpoint | Auth |
|---|---|---|
| GET | `/services` | Any |

### Example

```bash
# Login
curl -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=customer@test.com&password=password123"

# Book beautician 1
curl -X POST http://127.0.0.1:8000/booking \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"beautician_id": 1, "service_id": 1}'
```

---

## Design Decisions

### Why Redis distributed locking?

Without locking, two concurrent requests for the same beautician can both
pass the `is_available = True` check, both create bookings, and both
commit — a classic read-modify-write race condition.

Redis `SET NX EX` provides a fast, atomic lock. The lock value is a UUID,
and release is conditional on the value still matching — this prevents
releasing a lock acquired by a different process after a timeout.

The lock TTL is 60 seconds — well above the p99 booking latency of ~200ms.
For longer operations, a watchdog that extends the TTL would be needed.

### Why a 5-state machine instead of a boolean?

A boolean (`booked` / `not_booked`) can't express *why* a booking ended
(Completed vs Cancelled) or distinguish a pending acceptance from an
active service. A state machine models the real lifecycle and blocks
invalid jumps (`Requested → Completed` skips acceptance and service).

### Why PostgreSQL instead of SQLite?

SQLite serializes all writes at the file level — concurrent writes don't
actually race. That undermines the Redis lock story. PostgreSQL supports
true concurrent transactions, so the lock is solving a real problem.

### Why Alembic?

`Base.metadata.create_all()` can create tables but can't alter them.
Adding a column in production requires a migration. Alembic versions
every schema change, supports rollback, and is the standard for SQLAlchemy
projects.

---

## Known Limitations

- **No frontend** — backend only. The API is tested with `curl` and pytest.
- **No rate limiting** — a determined client could brute-force `/login`.
  Production would add a rate-limit middleware keyed on IP or user.
- **JWT is not revocable** — tokens are valid until expiry. Production
  would add a token blacklist or short-lived tokens with refresh.
- **Lock TTL is fixed at 60s** — a multi-minute booking operation could
  exceed this. Production would use Redlock or a watchdog.
- **No observability** — no metrics, tracing, or structured logs.
- **No deployment config** — no Dockerfile, Kubernetes manifests, or CI/CD.
- **Redis single instance** — a Redis outage takes down booking creation.
  Production would use Redis Sentinel or a managed service with failover.

---

## Future Improvements

- Add pagination to list endpoints
- Add rate limiting on auth
- Add refresh tokens
- Add structured logging (JSON) and Prometheus metrics
- Add OpenTelemetry tracing
- Add Dockerfile and docker-compose for one-command setup
- Add GitHub Actions CI to run tests on every push
- Add an admin endpoint to manually release stuck locks

---

## License

MIT