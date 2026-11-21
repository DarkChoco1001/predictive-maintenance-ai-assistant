# Security

This demo is built against the **OWASP Top 10 (2021)** and the **OWASP Top 10 for LLM Applications**. Each control below points to the code that implements it. Most are covered by automated tests in `backend/tests/test_api.py`.

## OWASP Top 10 (2021) mapping

| # | Risk | Controls in this project | Where |
|---|---|---|---|
| A01 | Broken Access Control | CORS allow-list (no wildcard, no credentials). A custom `X-Requested-With` header is required on every POST, which blocks cross-site request forgery. Only `GET`/`POST` are allowed. Unknown engines return 404. The CI token is read-only. | `main.py`, `security.py`, `ci.yml` |
| A02 | Cryptographic Failures | No secrets in code or in the browser bundle. The API key is read from the environment, server-side only. `.env` is git-ignored. HSTS can be switched on for HTTPS deployments. | `config.py`, `.gitignore`, `nginx.conf` |
| A03 | Injection | Every input is checked by strict Pydantic models: types, ranges, max lengths, no control characters, unknown fields rejected. There is no SQL or shell use. React escapes all output, `dangerouslySetInnerHTML` is never used, and a strict CSP blocks inline and third-party scripts. | `schemas.py`, `nginx.conf` |
| A04 | Insecure Design | Per-client rate limits (assistant 10/min, writes 30/min) at the app layer plus nginx `limit_req`. Request body capped at 16 KB, including chunked uploads. Bounded in-memory stores. The AI only drafts work orders; a person must approve them. | `security.py`, `workorders.py`, `nginx.conf` |
| A05 | Security Misconfiguration | Security headers on every response (CSP, `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, COOP/CORP). Server banners removed. API docs disabled in production. Trusted-host check. Generic error messages with no stack traces. Containers run as non-root, read-only, with all capabilities dropped and `no-new-privileges`. | `security.py`, `main.py`, `Dockerfile`s, `docker-compose.yml` |
| A06 | Vulnerable & Outdated Components | All dependencies pinned (`requirements.txt`, `package-lock.json`). CI runs `pip-audit`, `npm audit` and CodeQL. Dependabot opens weekly update PRs for pip, npm, Docker and Actions. | `ci.yml`, `dependabot.yml` |
| A07 | Identification & Authentication Failures | The demo has no user accounts (see *Known limitations*). Rate limiting slows brute-force-style abuse of the write endpoints. | — |
| A08 | Software & Data Integrity Failures | Models are exported as plain JSON. The backend never loads pickle files, so there is no unsafe deserialization. `npm ci --ignore-scripts` installs exactly what the lockfile says. AI output is schema-validated before use. | `ml/export_fleet.py`, `frontend/Dockerfile`, `assistant.py` |
| A09 | Security Logging & Monitoring Failures | Security events are logged (rate-limit hits, failed validation, missing CSRF header, oversized bodies, AI fallbacks, work-order creation). Logs never contain secrets, prompts or the technician's free text (only its length). 500 errors return a reference ID that matches the log line. | `security.py`, `main.py`, `assistant.py` |
| A10 | Server-Side Request Forgery | The only outbound calls (Anthropic API, Ollama) go to URLs fixed by the operator in environment variables. No request can supply or change a URL. | `config.py`, `assistant.py` |

## OWASP Top 10 for LLM Applications

| Risk | Control |
|---|---|
| LLM01 Prompt injection | The technician's question and retrieved documents are wrapped in tags and treated as data. The system prompt tells the model not to follow instructions inside them. The model has no tools and cannot take actions. |
| LLM02 Insecure output handling | Output must match a strict JSON schema, and the failure mode must be a known FMEA id. Anything invalid is discarded and the offline rules answer instead. The UI renders output as text only. |
| LLM04 Model denial of service | Rate limit on the assistant, 500-character question limit, request timeout, fixed `max_tokens`. |
| LLM06 Excessive agency | Work-order **priority and due date come from deterministic rules, not the model**. A manipulated prompt cannot downgrade an urgent job (tested in `test_llm_cannot_downgrade_priority`). A person approves every work order. |
| LLM09 Overreliance | Every answer lists its sources (FMEA record and procedures) and says which engine produced it. The UI states that the FMEA content is illustrative. |

## Known limitations (demo scope)

- **No authentication.** Anyone who can reach the app can view the fleet and create work orders. For a real deployment, put it behind single sign-on, e.g. an OIDC proxy such as oauth2-proxy with Entra ID or Google, and add role checks on `POST /api/work-orders`.
- **In-memory state.** Work orders and rate-limit counters reset on restart and are per process. Use a database and a shared store (e.g. Redis) when scaling out.
- **HTTP only by default.** Terminate TLS at a load balancer or reverse proxy, then set `ENABLE_HSTS=true` and enable the HSTS header in `nginx.conf`.

## Reporting a vulnerability

Please open a private security advisory on this repository rather than a public issue.
