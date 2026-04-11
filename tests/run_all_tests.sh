#!/bin/bash

# Avalon Game - Test Runner
# Runs all tests in the correct order

echo "🧪 Running Avalon Game Test Suite..."
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

run_test() {
    local test_name="$1"
    local test_command="$2"
    local test_dir="$3"
    
    echo -e "\n${YELLOW}Running: $test_name${NC}"
    echo "----------------------------------------"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if [ -n "$test_dir" ]; then
        cd "$test_dir"
    fi
    
    if eval "$test_command"; then
        echo -e "${GREEN}✅ PASSED: $test_name${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}❌ FAILED: $test_name${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    
    # Return to base directory
    cd "$(dirname "$0")"
}

# Check if backend is running
echo "🔍 Checking prerequisites..."
if ! curl -f http://localhost:8001/health >/dev/null 2>&1; then
    echo -e "${RED}❌ Backend not running on localhost:8001${NC}"
    echo "Please start the backend first: sudo supervisorctl start backend"
    exit 1
fi
echo -e "${GREEN}✅ Backend is running${NC}"

# Run Backend Tests
echo -e "\n📡 BACKEND TESTS"
echo "================"

run_test "Role Assignment Logic" "python role_assignment_test.py" "backend"
run_test "Bot Behavior" "python test_bots.py" "backend"
run_test "Backend API" "python backend_test.py" "backend"

# Run Integration Tests
echo -e "\n🔗 INTEGRATION TESTS"
echo "==================="

run_test "7-Player Scenario" "./test_seven_players.sh" "integration"
run_test "Deployment Validation" "./test-deploy.sh >/dev/null 2>&1 && echo 'Test completed'" "integration"

# Test Summary
echo -e "\n📊 TEST SUMMARY"
echo "==============="
echo -e "Total Tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "\n${GREEN}🎉 ALL TESTS PASSED!${NC}"
    exit 0
else
    echo -e "\n${RED}💥 SOME TESTS FAILED!${NC}"
    exit 1
fi