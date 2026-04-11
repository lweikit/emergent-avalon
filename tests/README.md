# Avalon Game - Test Suite

This directory contains all tests for the Avalon game application.

## Structure

```
tests/
├── backend/           # Backend-specific tests
│   ├── backend_test.py      # General backend API tests
│   ├── test_bots.py         # Bot behavior tests
│   └── role_assignment_test.py # Role assignment logic tests
├── frontend/          # Frontend-specific tests (future)
├── integration/       # Integration and end-to-end tests
│   ├── test_seven_players.py   # Multi-player scenario tests
│   ├── test_seven_players.sh   # Shell-based multi-player tests
│   └── test-deploy.sh          # Deployment testing
└── README.md         # This file
```

## Running Tests

### Backend Tests
```bash
# Run all backend tests
cd tests/backend
python backend_test.py

# Test bot functionality
python test_bots.py

# Test role assignment
python role_assignment_test.py
```

### Integration Tests
```bash
# Test 7-player scenario
cd tests/integration
python test_seven_players.py

# Or using shell script
./test_seven_players.sh

# Test deployment
./test-deploy.sh
```

### Prerequisites

1. **Backend running**: Ensure backend is running on localhost:8001
2. **Database**: MongoDB should be accessible
3. **Dependencies**: Install required packages from requirements.txt

### Test Coverage

#### Backend Tests
- ✅ API endpoint functionality
- ✅ Role assignment logic
- ✅ Bot behavior and AI
- ✅ Game state management
- ✅ WebSocket connections

#### Integration Tests
- ✅ Multi-player scenarios
- ✅ Session creation and joining
- ✅ Game flow from start to finish
- ✅ Deployment validation

### Adding New Tests

1. **Backend tests**: Add to `tests/backend/`
2. **Frontend tests**: Add to `tests/frontend/` (future)
3. **Integration tests**: Add to `tests/integration/`

### Test Environment

Tests use the development environment by default:
- Backend: `http://localhost:8001`
- Database: `mongodb://localhost:27017/avalon_game`

For production testing, update the URLs in individual test files.