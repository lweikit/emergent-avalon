# 🏰 Avalon Board Game

A production-ready, real-time multiplayer implementation of The Resistance: Avalon board game built with React, FastAPI, and MongoDB.

## ⚡ Quick Start

```bash
# Production deployment
chmod +x scripts/deploy.sh
./scripts/deploy.sh

# Development
sudo supervisorctl restart all

# Run tests
cd tests && ./run_all_tests.sh
```

## 📁 Project Structure

```
/
├── 📱 frontend/           # React application
├── 🔧 backend/            # FastAPI server
├── 🧪 tests/             # All tests (backend, frontend, integration)
├── 📚 docs/              # Documentation and configs
├── 🛠️ scripts/            # Deployment and utility scripts
├── 🐳 docker-compose.yml  # Container orchestration
└── 📖 README.md          # This file
```

## 🎮 Game Features

### Core Gameplay
- **Complete Avalon Experience**: All roles, missions, and game mechanics
- **5-10 Player Support**: Supports all player counts with proper role distribution
- **Spectator Mode**: Watch games without participating
- **Lady of the Lake**: Expansion content with persistent knowledge tracking
- **Assassination Phase**: Complete endgame mechanics with improved bot AI

### Advanced Features
- **Real-time Updates**: WebSocket support with API polling fallback
- **Session Management**: Create and join games with unique IDs
- **Reconnection Support**: Players can rejoin if disconnected
- **Auto-Cleanup**: Sessions automatically deleted after 7 days
- **Mobile Optimized**: Responsive design for all devices
- **Dynamic Role Balancing**: Intelligent role assignment based on win patterns

### Production Ready
- **Self-hosting**: Complete Docker setup with Cloudflare tunnel support
- **Security**: Proper role/vote privacy with no information leakage
- **Performance**: Optimized for concurrent players with race condition prevention
- **Monitoring**: Health checks and comprehensive logging

## 🎭 Roles Included

### Good Team
- **Merlin**: Sees all evil except Mordred and Oberon
- **Percival**: Sees Merlin and Morgana
- **Loyal Servants**: Trust in Merlin's guidance

### Evil Team
- **Morgana**: Appears as Merlin to Percival
- **Assassin**: Can kill Merlin if good wins
- **Mordred**: Hidden from Merlin
- **Oberon**: Hidden from everyone
- **Minions**: Work with other evil players

## 🚀 Deployment Options

### Option 1: Docker Compose (Recommended)
```bash
# Clone and deploy
git clone [your-repo]
cd avalon-game
./scripts/deploy.sh
```

### Option 2: Development Mode
```bash
# Backend
cd backend && pip install -r requirements.txt
sudo supervisorctl start backend

# Frontend  
cd frontend && yarn install && yarn start
```

### Option 3: Production with Cloudflare
```bash
# Set environment variables
export REACT_APP_BACKEND_URL=https://your-api-domain.com
export TUNNEL_TOKEN=your_cloudflare_token

# Deploy
./scripts/deploy.sh
```

## 🌐 Domain Configuration

Single domain with path-based routing:
- `https://avalon.weikit.me` — frontend
- `https://avalon.weikit.me/api` — backend (proxied via nginx/Cloudflare Tunnel)

## 🧪 Testing

```bash
# Run all tests
cd tests && ./run_all_tests.sh

# Backend tests only
cd tests/backend && python backend_test.py

# Integration tests
cd tests/integration && ./test_seven_players.sh

# Deployment test
cd tests/integration && ./test-deploy.sh
```

## 📊 Game Flow

1. **Lobby**: Players join and configure settings
2. **Role Assignment**: Secret roles distributed (spectators excluded)
3. **Mission Cycles**: 
   - Leader proposes team
   - All players vote on team
   - Team members vote on mission success/failure
4. **Lady of the Lake**: Reveal player allegiances (7+ players)
5. **Assassination**: Assassin attempts to kill Merlin
6. **Game End**: Victory determination with role reveals

## 🔧 Configuration

### Environment Variables
```env
# Backend
MONGO_URL=mongodb://localhost:27017/avalon_game
DB_NAME=avalon_game

# Frontend
REACT_APP_BACKEND_URL=https://your-backend-domain.com

# Optional: Cloudflare Tunnel
TUNNEL_TOKEN=your_tunnel_token
```

### Game Settings
- **Lady of the Lake**: Toggle in lobby (7+ players)
- **Dynamic Roles**: Mordred/Oberon based on win patterns
- **Session Cleanup**: Auto-delete after 7 days
- **Spectator Limit**: Unlimited spectators

## 🛠️ Development

### Prerequisites
- Docker & Docker Compose
- Node.js 20+ (for local development)
- Python 3.11+ (for local development)
- MongoDB 7.0+

### Local Development
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

### Adding Features
1. Backend changes: Edit `backend/server.py`
2. Frontend changes: Edit `frontend/src/App.js`
3. Tests: Add to appropriate `tests/` subdirectory
4. Documentation: Update relevant docs in `docs/`

## 🔐 Security Features

- **Role Privacy**: Players only see their own role during gameplay
- **Vote Security**: Individual mission votes never exposed
- **Lady of Lake Privacy**: Results only visible to user
- **Session Isolation**: Games are completely isolated
- **Input Validation**: All user inputs validated
- **Rate Limiting**: Prevents spam and abuse

## 📈 Performance

- **Concurrent Players**: Supports 10+ concurrent players per session
- **Multiple Sessions**: Unlimited concurrent game sessions
- **WebSocket Optimization**: Efficient real-time updates
- **Database Optimization**: Indexed queries and connection pooling
- **Memory Management**: Automatic cleanup of old sessions

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Make changes and add tests
4. Run test suite: `cd tests && ./run_all_tests.sh`
5. Submit pull request

## 📞 Support

For deployment help, check:
- `docs/DEPLOYMENT_GUIDE.md` - Complete deployment guide
- `tests/README.md` - Testing documentation
- Issues tab - Known issues and solutions

## 🎯 What's New

- ✅ **Fixed race conditions** in voting system
- ✅ **Optimized concurrent voting** - multiple players can vote simultaneously
- ✅ **Enhanced role security** - Merlin can no longer see Oberon
- ✅ **Persistent Lady of Lake** - Knowledge maintained throughout game
- ✅ **Organized repository** - Clean structure with proper test organization
- ✅ **Production deployment** - Docker and Cloudflare tunnel support

---

**Ready to play Avalon?** 🏰⚔️

Access the game at your configured domain or run locally at `http://localhost:3000`!

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

## Game Features

### Core Gameplay
1. **Create Session**: One player creates a game session
2. **Join Players**: 5-10 players join using the session ID
3. **Spectator Mode**: Additional players can join as spectators
4. **Start Game**: Roles are automatically assigned
5. **Missions**: Complete 5 missions with team selection and voting
6. **Win Conditions**: 
   - Good wins by completing 3 missions
   - Evil wins by failing 3 missions or forcing 5 vote rejections
   - Assassin can kill Merlin if good wins

### Advanced Features
- **Session ID Display**: Easily share session IDs for reconnection
- **Mobile Responsive**: Optimized for all screen sizes
- **Auto-Cleanup**: Sessions deleted after 7 days to save space
- **Bot Integration**: Test games with AI players
- **Real-time Sync**: WebSocket with API polling fallback

## Game Flow

1. **Lobby**: Players join and wait for game start
2. **Role Assignment**: Secret roles distributed (spectators don't get roles)
3. **Mission Cycles**: 
   - Leader proposes team
   - All players vote on team
   - Team members vote on mission success/failure
4. **Lady of the Lake**: Reveal player allegiances (7+ players)
5. **Assassination**: Assassin attempts to kill Merlin
6. **Game End**: Victory determination

## Production Deployment

### Using Cloudflare Tunnel (Recommended)

1. Set up a Cloudflare Tunnel:
   ```bash
   # Install cloudflared
   # Visit: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
   
   # Create tunnel and get token
   cloudflared tunnel create avalon-game
   ```

2. Add your tunnel token to `.env`:
   ```env
   TUNNEL_TOKEN=your_tunnel_token_here
   REACT_APP_BACKEND_URL=https://your-domain.com
   ```

3. Deploy:
   ```bash
   ./deploy.sh
   ```

### Self-Hosting Setup

1. Configure your reverse proxy (nginx/Apache) to point to:
   - Frontend: `localhost:3000`
   - Backend API: `localhost:8001`

2. Update `.env` with your domain:
   ```env
   REACT_APP_BACKEND_URL=https://your-domain.com/api
   ```

3. Ensure SSL certificates are configured

### Environment Variables

#### Required
- `MONGO_URL`: MongoDB connection string
- `DB_NAME`: Database name
- `REACT_APP_BACKEND_URL`: Backend API URL

#### Optional
- `TUNNEL_TOKEN`: Cloudflare tunnel token
- `MONGO_INITDB_ROOT_USERNAME`: MongoDB root username
- `MONGO_INITDB_ROOT_PASSWORD`: MongoDB root password

## Security Considerations

### Production Checklist
- [ ] Change default MongoDB credentials
- [ ] Use strong passwords
- [ ] Configure HTTPS/SSL
- [ ] Set up firewall rules
- [ ] Regular database backups
- [ ] Monitor resource usage
- [ ] Update dependencies regularly

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