# Deployment

## Architecture

Three environments sharing one Redis and one Supabase:

- **Vercel** — Next.js frontend, always on
- **Render** — Python harness + cloud brains, always on
- **Local** — Optional GPU brains, plug in when machine is on

```
Operator → Vercel (frontend) → Render (harness + cloud brains) → Redis + Supabase
                                              ↑
                              Local brains (Ollama) when machine is on
```

## Setup (one time)

### 1. Deploy harness to Render

1. Connect the GitHub repo to Render.
2. Render reads `render.yaml` and creates the web service + Redis automatically.
3. Set secrets in the Render dashboard:
   - `BLVCKSHELL_SUPABASE_URL`
   - `BLVCKSHELL_SUPABASE_KEY`
   - `BLVCKSHELL_ANTHROPIC_API_KEY`
   - `BLVCKSHELL_OPENAI_API_KEY` (optional)
   - `BLVCKSHELL_FRONTEND_URL` (your Vercel URL, e.g. `https://blvckshell.vercel.app`)
4. Confirm health: `GET https://<your-service>.onrender.com/health` returns `200`.

### 2. Deploy frontend to Vercel

1. Import the repo and set the **Root Directory** to `frontend`.
2. Set environment variable:
   - `NEXT_PUBLIC_HARNESS_URL=https://<your-harness>.onrender.com`
3. Deploy. The frontend talks only to the Render harness API.

### 3. (Optional) Run local brains

When your machine is on, local Ollama brains join the same registry over Render Redis:

1. Copy the Redis **external** connection string from the Render dashboard.
2. In local `.env`:
   ```bash
   BLVCKSHELL_REDIS_URL=redis://red-xxxxx.render.com:6379
   BLVCKSHELL_SUPABASE_URL=https://xxxxx.supabase.co
   BLVCKSHELL_SUPABASE_KEY=your-key
   BLVCKSHELL_OLLAMA_URL=http://localhost:11434
   BLVCKSHELL_OLLAMA_MODEL=qwen2.5:72b
   BLVCKSHELL_RUN_WORKERS_IN_PROCESS=false
   BLVCKSHELL_USE_IN_MEMORY_BUS=false
   ```
3. Run: `./scripts/run_local.sh venture`
4. Open the live frontend `/brains` — the local brain appears alongside cloud brains.

When your machine is off, cloud brains on Render handle everything.

## Environment variables

| Variable | Local dev | Render | Local brain (remote) |
|----------|-----------|--------|---------------------|
| `BLVCKSHELL_REDIS_URL` | `redis://localhost:6379` | Render internal (auto) | Render external URL |
| `BLVCKSHELL_SUPABASE_URL` | optional | required | required |
| `BLVCKSHELL_ANTHROPIC_API_KEY` | optional | required | optional |
| `BLVCKSHELL_OPENAI_API_KEY` | optional | optional | optional |
| `BLVCKSHELL_OLLAMA_URL` | optional | not set | `http://localhost:11434` |
| `BLVCKSHELL_FRONTEND_URL` | not set | Vercel URL | not set |
| `BLVCKSHELL_USE_IN_MEMORY_BUS` | `true` for tests | `false` | `false` |
| `BLVCKSHELL_RUN_WORKERS_IN_PROCESS` | `true` | `true` | `false` |
| `BLVCKSHELL_USE_FAKE_LLM` | `false` | `false` | `false` |
| `BLVCKSHELL_UPWORK_CLIENT_ID` / `_CLIENT_SECRET` | optional | optional (Research Brain) | not set |
| `BLVCKSHELL_UPWORK_REDIRECT_URI` / `_REFRESH_TOKEN` | optional | optional (Research Brain) | not set |
| `NEXT_PUBLIC_HARNESS_URL` | `http://localhost:8000` | N/A | N/A |

## Local development

No Render or Vercel required:

```bash
docker compose -f docker/docker-compose.yml up --build
```

This starts local Redis, the harness, and the frontend on `localhost`.

## CORS

When `BLVCKSHELL_FRONTEND_URL` is set (production on Render), the harness only
allows that origin plus `localhost` dev origins. Leave it blank in local dev
and CORS stays open (`*`).
