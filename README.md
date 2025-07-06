# Avalon Board Game

A real-time multiplayer implementation of The Resistance: Avalon board game built with React, FastAPI, and MongoDB.

## Features

- **Complete Avalon Gameplay**: All roles, missions, and game mechanics
- **Real-time Updates**: WebSocket support for live game state synchronization
- **Fallback Mode**: API polling when WebSocket connections fail
- **5-10 Player Support**: Supports all player counts with proper role distribution
- **Lady of the Lake**: Expansion content included
- **Assassination Phase**: Complete endgame mechanics
- **Session Management**: Create and join game sessions with unique IDs
- **Reconnection Support**: Players can rejoin if disconnected

## Roles Included

**Good Team:**
- Merlin (sees all evil except Mordred)
- Percival (sees Merlin and Morgana)
- Loyal Servants (trust in Merlin)

**Evil Team:**
- Morgana (appears as Merlin to Percival)
- Assassin (can kill Merlin if good wins)
- Mordred (hidden from Merlin)
- Oberon (hidden from everyone)
- Minions (work with other evil players)

## Quick Start with Docker Compose

1. Clone the repository
2. Copy `.env.example` to `.env` and adjust values if needed
3. Run the application:
   ```bash
   docker compose up --build -d
   ```
4. Access the game at http://localhost:3000

## Manual Setup

### Backend Setup

1. Install Python dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. Set up MongoDB and environment variables in `.env`:
   ```
   MONGO_URL=mongodb://localhost:27017
   DB_NAME=avalon_game
   ```

3. Run the backend:
   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8001 --reload
   ```

### Frontend Setup

1. Install Node.js dependencies:
   ```bash
   cd frontend
   yarn install
   ```

2. Ensure `REACT_APP_BACKEND_URL` is set in the root `.env` file:
   ```
   REACT_APP_BACKEND_URL=http://localhost:8001
   ```

3. Run the frontend:
   ```bash
   yarn start
   ```

## How to Play

1. **Create Session**: One player creates a game session
2. **Join Players**: 5-10 players join using the session ID
3. **Start Game**: Roles are automatically assigned
4. **Missions**: Complete 5 missions with team selection and voting
5. **Win Conditions**: 
   - Good wins by completing 3 missions
   - Evil wins by failing 3 missions or forcing 5 vote rejections
   - Assassin can kill Merlin if good wins

## Game Flow

1. **Lobby**: Players join and wait for game start
2. **Role Assignment**: Secret roles distributed
3. **Mission Cycles**: 
   - Leader proposes team
   - All players vote on team
   - Team members vote on mission success/failure
4. **Lady of the Lake**: Reveal player allegiances (7+ players)
5. **Assassination**: Assassin attempts to kill Merlin
6. **Game End**: Victory determination

## Technical Architecture

- **Frontend**: React 19 with Tailwind CSS
- **Backend**: FastAPI with WebSocket support
- **Database**: MongoDB for game state persistence
- **Real-time**: WebSocket connections with API polling fallback

## API Endpoints

- `POST /api/create-session` - Create new game session
- `POST /api/join-session` - Join existing session
- `POST /api/start-game` - Start the game
- `POST /api/select-team` - Propose mission team
- `POST /api/vote-team` - Vote on proposed team
- `POST /api/vote-mission` - Vote on mission outcome
- `POST /api/lady-of-lake` - Use Lady of the Lake
- `POST /api/assassinate` - Assassin kills target
- `GET /api/session/{id}` - Get session details
- `WS /ws/{session_id}` - WebSocket connection

## Environment Variables

### Backend
- `MONGO_URL`: MongoDB connection string
- `DB_NAME`: Database name

### Frontend
- `REACT_APP_BACKEND_URL`: Backend API URL

Create a `.env` file in the project root (you can copy `/.env.example`) to
override these variables when running `docker compose`. Changes to
`REACT_APP_BACKEND_URL` require restarting the `frontend` service so the React
app picks up the new value.

## Development

The application supports hot reload for development:
- Backend: FastAPI with `--reload` flag
- Frontend: React development server

## Deployment

Use Docker Compose for easy deployment:
```bash
docker compose up -d
```

Services will be available at:
- Frontend: http://localhost:3000
- Backend: http://localhost:8001
- MongoDB: localhost:27017

If you provide a Cloudflare Tunnel token in `.env`, the optional `cloudflared`
service will expose the frontend through Cloudflare.

## License

MIT License - see LICENSE file for details.