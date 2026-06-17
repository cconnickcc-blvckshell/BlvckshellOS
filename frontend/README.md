# Blvckshell Command Interface

The operator's command center for the harness. Dark. Precise. Alive.

## Views

- **Intake** (`/`) — full-screen single input with a voice button (Web Speech
  API). Drop an idea; the harness takes over.
- **Pipelines** (`/pipelines`) — live view of active pipelines with breathing
  brain status orbs (idle / thinking / executing / error) and per-run synthesis.
- **Judgment Ledger** (`/ledger`) — every belief, confidence, and outcome,
  filterable by brain.
- **Doctrine** (`/doctrine`) — promoted, validated beliefs. Append-only feel.
- **Observer** (`/observer`) — the real-time audit stream (SSE), every event.

## Develop

```bash
npm install
NEXT_PUBLIC_HARNESS_URL=http://localhost:8000 npm run dev
# → http://localhost:3000
```

The interface talks to the harness API at `NEXT_PUBLIC_HARNESS_URL`.

## Design tokens

Defined in `tailwind.config.ts`:

| Token            | Value     |
|------------------|-----------|
| background       | `#080810` |
| surface          | `#0F0F1A` |
| border           | `#1A1A2E` |
| primary accent   | `#7B2FBE` |
| active accent    | `#A855F7` |
| text primary     | `#E8E8F0` |
| text secondary   | `#6B6B8A` |
| success/warn/err | `#22C55E` / `#F59E0B` / `#EF4444` |

Type: Space Grotesk (display), Inter (body), JetBrains Mono (mono).
