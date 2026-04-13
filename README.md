# Avalon Board Game

A real-time multiplayer implementation of The Resistance: Avalon. Built with TypeScript/React, FastAPI, MongoDB, and Docker.

## Quick Start

```bash
cp .env.example .env    # edit credentials before deploying
docker compose up -d
```

Open `http://localhost:3000`. For external access, set `TUNNEL_TOKEN` in `.env` and run with the tunnel profile:

```bash
docker compose --profile tunnel up -d
```

## Game Features

- **5-10 players** with correct role distribution per official Avalon rules
- **Spectator mode** — watch without participating
- **Real-time** via WebSocket, with automatic polling fallback
- **Session persistence** — survives page refresh (localStorage)
- **Reconnection** — rejoin by name if disconnected
- **Mobile friendly** — responsive layout, 48px tap targets
- **Auto-cleanup** — sessions deleted after 7 days

### Roles

| Good | Evil |
|------|------|
| Merlin (sees evil except Mordred/Oberon) | Morgana (appears as Merlin to Percival) |
| Percival (sees Merlin and Morgana) | Assassin (kills Merlin if good wins) |
| Loyal Servants | Mordred (hidden from Merlin, toggleable) |
| | Oberon (hidden from everyone, toggleable) |
| | Minions |

### Game Flow

1. **Lobby** — players join, configure settings (Lady of the Lake, Mordred, Oberon toggles)
2. **Team Selection** — leader proposes a team
3. **Team Vote** — all players approve/reject, results revealed simultaneously
4. **Mission** — team members secretly vote success/fail (good must vote success)
5. **Mission Reveal** — result shown with vote counts before advancing
6. **Lady of the Lake** (7+ players, after missions 2/3/4) — reveal a player's allegiance
7. **Assassination** — if good wins 3 missions, assassin picks Merlin
8. **Game End** — roles revealed, win reason shown

5 rejected teams in a row = evil wins automatically.

## Architecture

```
frontend/          TypeScript React app (CRA + Tailwind)
  src/
    components/    MainMenu, Lobby, GameBoard
    hooks/         useWebSocket
    api.ts         Typed API layer
    types.ts       Shared interfaces

backend/           Python FastAPI
  server.py        Routes, WebSocket, lifecycle
  models.py        Pydantic models, game config tables
  game_logic.py    Pure functions: role assignment, vote processing, phase transitions
  bots.py          Bot AI for all game phases
  websocket.py     Connection manager, personalized broadcasts
  auth.py          Token issue/verify/cleanup
```

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGO_INITDB_ROOT_PASSWORD` | Yes | MongoDB password (change from default) |
| `MONGO_URL` | Yes | Connection string matching the password above |
| `DB_NAME` | No | Database name (default: `avalon_game`) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |
| `TUNNEL_TOKEN` | No | Cloudflare tunnel token for external access |

## Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn server:app --reload --port 8001

# Frontend
cd frontend
yarn install
yarn start
```

## Testing

```bash
# Unit tests (no infra needed, pure game logic)
cd backend && python -m pytest ../tests/test_game_logic.py -v

# Integration tests (needs docker compose up)
python tests/test_integration.py

# End-to-end WebSocket tests (needs docker compose up)
python tests/test_e2e.py
```

139 unit + 163 integration + 23 e2e = **325 tests**.

## Security

- Player tokens required on all mutation endpoints
- WebSocket identify verified with token (connection closed on failure)
- Roles hidden during gameplay — only your own role visible
- Individual mission votes never exposed — only aggregate pass/fail counts
- Lady of the Lake knowledge only sent to the holder
- Good players cannot vote fail (server-enforced)
- Session-level locking on all state mutations
- Rate limiting (200 req/min per IP)

## Domain Setup

Single domain with nginx path-based routing:

- `https://your-domain.com` — frontend
- `https://your-domain.com/api/*` — backend proxy

See [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) for Cloudflare Tunnel configuration.

---

MIT License — see [LICENSE](LICENSE) for details.
