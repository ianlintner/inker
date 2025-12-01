## Copilot / AI Agent Instructions for this repository

Short, actionable instructions to help an AI coding agent be productive in the Inker (AI Blogger) repo.

1. Big picture
   - This project is an AI-driven blog generator implemented as a Python package `ai_blogger` with a small React frontend in `frontend/`.
   - Core pipeline (see `ai_blogger/__main__.py`): fetch articles -> generate candidate posts -> score -> refine winner -> write Markdown.
   - Fetchers are pluggable (see `ai_blogger/fetchers.py`). Chains with LLM prompts live in `ai_blogger/chains.py`. Pydantic models live in `ai_blogger/models.py`.

2. Where to start editing code
   - LLM behavior & prompts: `ai_blogger/chains.py` (generate/score/refine). Small, well-scoped functions.
   - New data sources: implement `BaseFetcher` in `ai_blogger/fetchers.py` and register with the `@register_fetcher` pattern used there.
   - Persistence: use `ai_blogger/persistence/factory.py` (auto-detects `DATABASE_URL` vs SQLite). Concrete backends: `sqlite_storage.py`, `postgres_storage.py`.
   - Queues: use `ai_blogger/queue/factory.py` (auto-detects `REDIS_URL`, `DATABASE_URL`, falls back to memory). Concrete backends: `memory_queue.py`, `postgres_queue.py`, `redis_queue.py`.

3. Important developer workflows & commands
   - Run the CLI locally (Python 3.9+):
     - Install deps: `python -m pip install -r requirements.txt` (or use `pip install -e .` in a venv)
     - Required env: `OPENAI_API_KEY` (required). Optional: `TAVILY_API_KEY`, `YOUTUBE_API_KEY`, `REDIS_URL`, `DATABASE_URL`.
     - Example CLI: `OPENAI_API_KEY=xxx python -m ai_blogger --num-posts 3 --out-dir ./out --verbose`
     - Helpful flags: `--list-sources`, `--dry-run`, `--max-results "hacker_news:15,youtube:5"` (see `__main__.py`).
   - Frontend dev server: `cd frontend && npm install && npm run dev` (Vite + React).
   - Tests: run unit & integration tests with pytest from repo root: `pytest tests/ -v`. BDD features live under `tests/features/` and step defs under `step_defs/`.

4. Project-specific conventions and patterns
   - Auto-detection: Storage and Queue factories decide implementation by environment variables (DATABASE_URL, REDIS_URL). When writing code that constructs storage/queue, prefer using `create_storage()` / `create_queue()`.
   - Environment-first behavior: CLI exits early if `OPENAI_API_KEY` missing; other sources are disabled with warnings.
   - Pydantic models are used as domain objects (`ai_blogger/models.py`) — prefer them for function signatures and serialization.
   - DB schema migrations: `postgres_storage.PostgresStorage.initialize()` will auto-run schema creation when `auto_migrate=True`.

5. Testing & mocking guidance (concrete)
   - Mock outbound HTTP / LLM calls in unit tests. Examples in tests mock `requests.get`, Tavily client, and LLM clients.
   - To run a single test file: `pytest tests/test_fetchers_integration.py -q` or use `-k` to filter tests (e.g. `-k hacker_news`).

6. Files worth reading for context
   - `ai_blogger/__main__.py` — entrypoint & CLI examples
   - `ai_blogger/fetchers.py` — fetcher registration pattern and per-source env keys
   - `ai_blogger/chains.py` — prompts and LLM orchestration
   - `ai_blogger/persistence/factory.py` and `ai_blogger/queue/factory.py` — env-driven backend selection
   - `ai_blogger/persistence/postgres_storage.py` — production schema & migration code
   - `frontend/package.json` — frontend commands (Vite)
   - `pyproject.toml` — dev tooling (black/isort/mypy/pytest) and optional `observability` extras
   - `.github/agents/ai-blogger-agent.md` — an existing agent-focused document with additional details

7. When changing behavior that touches infra
   - If adding Postgres or Redis dependencies mention required env vars: `DATABASE_URL` (Postgres), `REDIS_URL` (Redis), and `INKER_DB_PATH` for local SQLite override.
   - When modifying DB schema, update `SCHEMA_VERSION` and the migration logic in `postgres_storage.py`.

8. Minimal coaching for PRs
   - Keep changes small and unit-tested. Use existing pytest markers (integration) when tests touch external services.
   - Preserve type hints and docstrings. Follow Black formatting (120 cols) and isort profile=black (see `pyproject.toml`).

If anything above is unclear or you'd like more examples (e.g., a short walkthrough for adding a new fetcher or writing a unit test that mocks the LLM), tell me which section to expand and I will iterate.
