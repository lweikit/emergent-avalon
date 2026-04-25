import { useRef, useEffect, useState, useCallback } from "react";
import { getWsBaseUrl } from "../api";
import { GameState } from "../types";

interface UseWebSocketReturn {
  isConnected: boolean;
  gameState: GameState | null;
}

interface WsIdentifyMessage {
  type: "identify";
  player_id: string;
  player_token: string;
}

interface WsPongMessage {
  type: "pong";
}

type WsOutgoingMessage = WsIdentifyMessage | WsPongMessage;

export default function useWebSocket(
  sessionId: string | null,
  playerId: string | null,
  playerToken: string | null
): UseWebSocketReturn {
  const ws = useRef<WebSocket | null>(null);
  const retryCount = useRef(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [gameState, setGameState] = useState<GameState | null>(null);

  const connect = useCallback(() => {
    if (!sessionId) return;

    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }

    const wsBaseUrl = getWsBaseUrl();
    const url = playerId
      ? `${wsBaseUrl}/api/ws/${sessionId}?player_id=${playerId}`
      : `${wsBaseUrl}/api/ws/${sessionId}`;
    const socket = new WebSocket(url);
    ws.current = socket;

    socket.onopen = () => {
      setIsConnected(true);
      retryCount.current = 0;
      if (playerId && playerToken) {
        const msg: WsOutgoingMessage = { type: "identify", player_id: playerId, player_token: playerToken };
        socket.send(JSON.stringify(msg));
      }
    };

    socket.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "game_state") {
          setGameState(data as GameState);
        } else if (data.type === "ping") {
          if (socket.readyState === WebSocket.OPEN) {
            const msg: WsOutgoingMessage = { type: "pong" };
            socket.send(JSON.stringify(msg));
          }
        }
      } catch (_) { /* ignore malformed messages */ }
    };

    socket.onclose = (event: CloseEvent) => {
      setIsConnected(false);
      if (event.code !== 1000) {
        const delay = Math.min(1000 * Math.pow(2, retryCount.current), 30000);
        retryCount.current += 1;
        retryTimer.current = setTimeout(connect, delay);
      }
    };

    socket.onerror = () => {
      setIsConnected(false);
    };
  }, [sessionId, playerId, playerToken]);

  useEffect(() => {
    setGameState(null);
    setIsConnected(false);
    connect();
    return () => {
      if (retryTimer.current) {
        clearTimeout(retryTimer.current);
      }
      if (ws.current) {
        ws.current.close(1000);
        ws.current = null;
      }
    };
  }, [connect]);

  return { isConnected, gameState };
}
