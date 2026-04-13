import axios, { AxiosResponse } from "axios";
import { Session, GameState } from "./types";

interface CreateSessionResponse {
  session_id: string;
  player_id: string;
  player_token: string;
}

interface JoinSessionResponse {
  player_id: string;
  player_token: string;
}

interface LadyOfLakeResponse {
  target_name: string;
  allegiance: string;
}

const getBackendUrl = (): string => {
  if (typeof window !== "undefined" && window._env_?.REACT_APP_BACKEND_URL) {
    return window._env_.REACT_APP_BACKEND_URL;
  }
  if (typeof process !== "undefined" && process.env?.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL;
  }
  return "";
};

export const getWsBaseUrl = (): string => {
  const backendUrl = getBackendUrl();
  if (backendUrl) {
    return backendUrl.replace("https://", "wss://").replace("http://", "ws://");
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}`;
};

const apiUrl = `${getBackendUrl()}/api`;

const api = {
  createSession: (name: string, playerName: string): Promise<AxiosResponse<CreateSessionResponse>> =>
    axios.post(`${apiUrl}/create-session`, { name, player_name: playerName }),

  joinSession: (sessionId: string, playerName: string, asSpectator: boolean): Promise<AxiosResponse<JoinSessionResponse>> =>
    axios.post(`${apiUrl}/join-session`, { session_id: sessionId, player_name: playerName, as_spectator: asSpectator }),

  startGame: (sessionId: string): Promise<AxiosResponse<void>> =>
    axios.post(`${apiUrl}/start-game`, { session_id: sessionId }),

  startTestGame: (sessionId: string): Promise<AxiosResponse<void>> =>
    axios.post(`${apiUrl}/start-test-game`, { session_id: sessionId }),

  selectTeam: (sessionId: string, playerId: string, playerToken: string, teamMembers: string[]): Promise<AxiosResponse<void>> =>
    axios.post(`${apiUrl}/select-team`, { session_id: sessionId, player_id: playerId, player_token: playerToken, team_members: teamMembers }),

  voteTeam: (sessionId: string, playerId: string, playerToken: string, vote: boolean): Promise<AxiosResponse<void>> =>
    axios.post(`${apiUrl}/vote-team`, { session_id: sessionId, player_id: playerId, player_token: playerToken, vote }),

  voteMission: (sessionId: string, playerId: string, playerToken: string, vote: boolean): Promise<AxiosResponse<void>> =>
    axios.post(`${apiUrl}/vote-mission`, { session_id: sessionId, player_id: playerId, player_token: playerToken, vote }),

  ladyOfLake: (sessionId: string, playerId: string, playerToken: string, targetId: string): Promise<AxiosResponse<LadyOfLakeResponse>> =>
    axios.post(`${apiUrl}/lady-of-lake`, { session_id: sessionId, player_id: playerId, player_token: playerToken, target_player_id: targetId }),

  assassinate: (sessionId: string, playerId: string, playerToken: string, targetId: string): Promise<AxiosResponse<void>> =>
    axios.post(`${apiUrl}/assassinate`, { session_id: sessionId, player_id: playerId, player_token: playerToken, target_player_id: targetId }),

  toggleLadyOfLake: (sessionId: string, enabled: boolean): Promise<AxiosResponse<void>> =>
    axios.post(`${apiUrl}/toggle-lady-of-lake`, { session_id: sessionId, enabled }),

  toggleMordred: (sessionId: string, enabled: boolean): Promise<AxiosResponse<void>> =>
    axios.post(`${apiUrl}/toggle-mordred`, { session_id: sessionId, enabled }),

  toggleOberon: (sessionId: string, enabled: boolean): Promise<AxiosResponse<void>> =>
    axios.post(`${apiUrl}/toggle-oberon`, { session_id: sessionId, enabled }),

  restartGame: (sessionId: string): Promise<AxiosResponse<void>> =>
    axios.post(`${apiUrl}/restart-game`, { session_id: sessionId }),

  endGame: (sessionId: string): Promise<AxiosResponse<void>> =>
    axios.post(`${apiUrl}/end-game`, { session_id: sessionId }),

  getSession: (sessionId: string): Promise<AxiosResponse<Session>> =>
    axios.get(`${apiUrl}/session/${sessionId}`),

  getSessionPersonalized: (sessionId: string, playerId: string, playerToken: string): Promise<AxiosResponse<GameState>> =>
    axios.get(`${apiUrl}/session/${sessionId}/me`, { params: { player_id: playerId, player_token: playerToken } }),
};

export default api;
