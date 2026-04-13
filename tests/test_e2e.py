#!/usr/bin/env python3
"""End-to-end tests that exercise WebSocket connections and full game flows.

Tests what the actual browser does — WebSocket connect, identify, receive state,
and play through a complete game.
"""

import asyncio
import json
import requests
import websockets
import time
import sys

BASE = "http://localhost:3000/api"
WS_BASE = "ws://localhost:3000/api/ws"
PASSED = 0
FAILED = 0


def check(label, condition):
    global PASSED, FAILED
    if condition:
        PASSED += 1
    else:
        FAILED += 1
        print(f"  FAIL: {label}")


async def test_websocket_connect_and_identify():
    """Test that WebSocket connects, identifies, and receives game state."""
    print("\n=== WebSocket Connect & Identify ===")

    # Create session via HTTP
    res = requests.post(f"{BASE}/create-session", json={"name": "WS Test", "player_name": "Alice"}).json()
    sid = res["session_id"]
    pid = res["player_id"]
    tok = res["player_token"]

    # Connect WebSocket
    ws_url = f"{WS_BASE}/{sid}?player_id={pid}"
    try:
        async with websockets.connect(ws_url) as ws:
            # Should receive initial game state broadcast
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            check("received game_state on connect", data.get("type") == "game_state")
            check("session id matches", data.get("session", {}).get("id") == sid)

            # Send identify with token
            await ws.send(json.dumps({"type": "identify", "player_id": pid, "player_token": tok}))

            # Should receive updated state after identify
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            check("received state after identify", data.get("type") == "game_state")

            # Verify connection is still alive
            check("websocket still open", not ws.close_code)

    except Exception as e:
        check(f"websocket connection succeeded (got: {e})", False)


async def test_websocket_bad_token_rejected():
    """Test that identify with wrong token is rejected."""
    print("\n=== WebSocket Bad Token Rejected ===")

    res = requests.post(f"{BASE}/create-session", json={"name": "Bad Token", "player_name": "Bob"}).json()
    sid = res["session_id"]
    pid = res["player_id"]

    ws_url = f"{WS_BASE}/{sid}?player_id={pid}"
    async with websockets.connect(ws_url) as ws:
        # Consume initial broadcasts
        for _ in range(3):
            try:
                await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                break

        # Send identify with wrong token
        await ws.send(json.dumps({"type": "identify", "player_id": pid, "player_token": "wrong-token"}))

        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(msg)
        check("bad token returns error", data.get("type") == "error")


async def test_websocket_receives_realtime_updates():
    """Test that a connected player receives updates when another player joins."""
    print("\n=== WebSocket Real-time Updates ===")

    res = requests.post(f"{BASE}/create-session", json={"name": "RT Test", "player_name": "P1"}).json()
    sid = res["session_id"]
    pid1 = res["player_id"]
    tok1 = res["player_token"]

    ws_url = f"{WS_BASE}/{sid}?player_id={pid1}"
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"type": "identify", "player_id": pid1, "player_token": tok1}))
        # Consume initial broadcasts
        for _ in range(3):
            try:
                await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                break

        # Another player joins via HTTP
        requests.post(f"{BASE}/join-session", json={"session_id": sid, "player_name": "P2"})

        # Should receive update with 2 players
        msg = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(msg)
        check("received update after P2 joined", data.get("type") == "game_state")
        players = data.get("session", {}).get("players", [])
        check("state shows 2 players", len(players) == 2)


async def test_connection_status_updates():
    """Test that is_connected flag updates on connect/disconnect."""
    print("\n=== Connection Status ===")

    res = requests.post(f"{BASE}/create-session", json={"name": "Conn Test", "player_name": "P1"}).json()
    sid = res["session_id"]
    pid1 = res["player_id"]
    tok1 = res["player_token"]

    res2 = requests.post(f"{BASE}/join-session", json={"session_id": sid, "player_name": "P2"}).json()
    pid2 = res2["player_id"]
    tok2 = res2["player_token"]

    # P1 connects
    ws_url1 = f"{WS_BASE}/{sid}?player_id={pid1}"
    ws1 = await websockets.connect(ws_url1)
    await ws1.send(json.dumps({"type": "identify", "player_id": pid1, "player_token": tok1}))
    # Drain broadcasts
    for _ in range(3):
        try:
            await asyncio.wait_for(ws1.recv(), timeout=2)
        except asyncio.TimeoutError:
            break

    # P2 connects then disconnects
    ws_url2 = f"{WS_BASE}/{sid}?player_id={pid2}"
    ws2 = await websockets.connect(ws_url2)
    await ws2.send(json.dumps({"type": "identify", "player_id": pid2, "player_token": tok2}))
    await asyncio.sleep(0.5)
    # Drain
    for _ in range(5):
        try:
            await asyncio.wait_for(ws1.recv(), timeout=1)
        except asyncio.TimeoutError:
            break

    # Close P2's connection
    await ws2.close()
    await asyncio.sleep(1)

    # P1 should get an update showing P2 as disconnected
    try:
        msg = await asyncio.wait_for(ws1.recv(), timeout=5)
        data = json.loads(msg)
        p2_data = next((p for p in data.get("session", {}).get("players", []) if p["id"] == pid2), None)
        check("P2 shows as disconnected after WS close", p2_data is not None and p2_data["is_connected"] is False)
    except asyncio.TimeoutError:
        check("received disconnect broadcast for P2", False)

    await ws1.close()


async def test_vote_reveal_over_websocket():
    """Test that vote reveal phase is broadcast with individual votes visible."""
    print("\n=== Vote Reveal via WebSocket ===")

    # Create 5-player game
    res = requests.post(f"{BASE}/create-session", json={"name": "Reveal Test", "player_name": "P1"}).json()
    sid = res["session_id"]
    tokens = {"P1": (res["player_id"], res["player_token"])}
    for name in ["P2", "P3", "P4", "P5"]:
        r = requests.post(f"{BASE}/join-session", json={"session_id": sid, "player_name": name}).json()
        tokens[name] = (r["player_id"], r["player_token"])

    # Connect P1 via WebSocket
    pid1, tok1 = tokens["P1"]
    ws_url = f"{WS_BASE}/{sid}?player_id={pid1}"
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"type": "identify", "player_id": pid1, "player_token": tok1}))

        # Start game
        requests.post(f"{BASE}/start-game", json={"session_id": sid})

        # Drain broadcasts to get current state
        state = None
        for _ in range(5):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(msg)
                if data.get("type") == "game_state":
                    state = data
            except asyncio.TimeoutError:
                break

        check("got game state after start", state is not None)
        if not state:
            return

        session = state["session"]
        check("phase is mission_team_selection", session["phase"] == "mission_team_selection")

        # Find leader and select team
        leader = session["players"][session["current_leader"]]
        lname = next(n for n, (p, _) in tokens.items() if p == leader["id"])
        lpid, ltok = tokens[lname]
        active = [p for p in session["players"] if not p["is_spectator"]]
        team = [active[0]["id"], active[1]["id"]]

        requests.post(f"{BASE}/select-team", json={
            "session_id": sid, "player_id": lpid, "player_token": ltok,
            "team_members": team
        })

        # Drain to get voting phase
        for _ in range(3):
            try:
                await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                break

        # All vote approve
        for name, (pid, tok) in tokens.items():
            requests.post(f"{BASE}/vote-team", json={
                "session_id": sid, "player_id": pid, "player_token": tok, "vote": True
            })

        # Should receive vote_reveal state with individual votes
        reveal_state = None
        for _ in range(5):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3)
                data = json.loads(msg)
                if data.get("type") == "game_state" and data["session"]["phase"] == "vote_reveal":
                    reveal_state = data
                    break
            except asyncio.TimeoutError:
                break

        check("received vote_reveal phase", reveal_state is not None)
        if reveal_state:
            mission = reveal_state["session"]["missions"][0]
            check("individual votes visible in reveal", len(mission.get("votes", {})) == 5)
            check("team marked as approved", mission.get("team_approved") is True)

        # Wait for auto-advance
        exec_state = None
        for _ in range(10):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(msg)
                if data.get("type") == "game_state" and data["session"]["phase"] == "mission_execution":
                    exec_state = data
                    break
            except asyncio.TimeoutError:
                continue

        check("auto-advanced to mission_execution after reveal", exec_state is not None)


async def test_personalized_state_via_websocket():
    """Test that each player receives their own role info, not others'."""
    print("\n=== Personalized State via WebSocket ===")

    res = requests.post(f"{BASE}/create-session", json={"name": "Personal Test", "player_name": "P1"}).json()
    sid = res["session_id"]
    tokens = {"P1": (res["player_id"], res["player_token"])}
    for name in ["P2", "P3", "P4", "P5"]:
        r = requests.post(f"{BASE}/join-session", json={"session_id": sid, "player_name": name}).json()
        tokens[name] = (r["player_id"], r["player_token"])

    requests.post(f"{BASE}/start-game", json={"session_id": sid})

    # Connect two different players and check they get different role info
    pid1, tok1 = tokens["P1"]
    pid2, tok2 = tokens["P2"]

    async with websockets.connect(f"{WS_BASE}/{sid}?player_id={pid1}") as ws1, \
               websockets.connect(f"{WS_BASE}/{sid}?player_id={pid2}") as ws2:

        await ws1.send(json.dumps({"type": "identify", "player_id": pid1, "player_token": tok1}))
        await ws2.send(json.dumps({"type": "identify", "player_id": pid2, "player_token": tok2}))

        # Get state for P1
        state1 = None
        for _ in range(5):
            try:
                msg = await asyncio.wait_for(ws1.recv(), timeout=2)
                data = json.loads(msg)
                if data.get("role_info"):
                    state1 = data
                    break
            except asyncio.TimeoutError:
                break

        # Get state for P2
        state2 = None
        for _ in range(5):
            try:
                msg = await asyncio.wait_for(ws2.recv(), timeout=2)
                data = json.loads(msg)
                if data.get("role_info"):
                    state2 = data
                    break
            except asyncio.TimeoutError:
                break

        check("P1 received role info", state1 is not None and "role_info" in state1)
        check("P2 received role info", state2 is not None and "role_info" in state2)

        if state1 and state2:
            # Each player should only see their own role in the players list
            p1_players = state1["session"]["players"]
            own_role = next((p["role"] for p in p1_players if p["id"] == pid1), "MISSING")
            other_roles = [p["role"] for p in p1_players if p["id"] != pid1]
            check("P1 sees own role", own_role is not None)
            check("P1 does NOT see other roles", all(r is None for r in other_roles))


async def test_polling_fallback_personalized():
    """Test the /me endpoint returns personalized state with role info."""
    print("\n=== Polling Fallback /me Endpoint ===")

    res = requests.post(f"{BASE}/create-session", json={"name": "Me Test", "player_name": "P1"}).json()
    sid = res["session_id"]
    tokens = {"P1": (res["player_id"], res["player_token"])}
    for name in ["P2", "P3", "P4", "P5"]:
        r = requests.post(f"{BASE}/join-session", json={"session_id": sid, "player_name": name}).json()
        tokens[name] = (r["player_id"], r["player_token"])

    requests.post(f"{BASE}/start-game", json={"session_id": sid})
    time.sleep(0.5)

    pid1, tok1 = tokens["P1"]
    # Test personalized endpoint
    res = requests.get(f"{BASE}/session/{sid}/me", params={"player_id": pid1, "player_token": tok1})
    check("/me returns 200", res.status_code == 200)
    data = res.json()
    check("/me includes role_info", "role_info" in data)
    check("/me includes session", "session" in data)

    # Test with wrong token
    res_bad = requests.get(f"{BASE}/session/{sid}/me", params={"player_id": pid1, "player_token": "wrong"})
    check("/me rejects bad token with 403", res_bad.status_code == 403)

    # Test public endpoint doesn't leak roles
    res_pub = requests.get(f"{BASE}/session/{sid}")
    pub_data = res_pub.json()
    roles_visible = [p["role"] for p in pub_data["players"] if p["role"] is not None]
    check("public endpoint hides roles during game", len(roles_visible) == 0)


async def main():
    print("Avalon End-to-End Tests")
    print("=======================")
    print(f"HTTP: {BASE}")
    print(f"WS:   {WS_BASE}")

    # Verify API is up
    try:
        r = requests.get(f"{BASE}/")
        assert r.status_code == 200
    except Exception as e:
        print(f"Cannot connect to API: {e}")
        sys.exit(1)

    await test_websocket_connect_and_identify()
    await test_websocket_bad_token_rejected()
    await test_websocket_receives_realtime_updates()
    await test_connection_status_updates()
    await test_vote_reveal_over_websocket()
    await test_personalized_state_via_websocket()
    await test_polling_fallback_personalized()

    print(f"\n{'=' * 40}")
    print(f"PASSED: {PASSED}")
    print(f"FAILED: {FAILED}")
    print(f"TOTAL:  {PASSED + FAILED}")
    print(f"{'=' * 40}")

    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
