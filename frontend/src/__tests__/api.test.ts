import axios from "axios";
import api from "../api";

jest.mock("axios");
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe("api module", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("method existence", () => {
    it("exports all expected API methods", () => {
      expect(typeof api.createSession).toBe("function");
      expect(typeof api.joinSession).toBe("function");
      expect(typeof api.startGame).toBe("function");
      expect(typeof api.startTestGame).toBe("function");
      expect(typeof api.selectTeam).toBe("function");
      expect(typeof api.voteTeam).toBe("function");
      expect(typeof api.voteMission).toBe("function");
      expect(typeof api.ladyOfLake).toBe("function");
      expect(typeof api.assassinate).toBe("function");
      expect(typeof api.toggleLadyOfLake).toBe("function");
      expect(typeof api.toggleMordred).toBe("function");
      expect(typeof api.toggleOberon).toBe("function");
      expect(typeof api.restartGame).toBe("function");
      expect(typeof api.endGame).toBe("function");
      expect(typeof api.leaveSession).toBe("function");
      expect(typeof api.getSession).toBe("function");
      expect(typeof api.getSessionPersonalized).toBe("function");
    });
  });

  describe("createSession", () => {
    it("calls POST /api/create-session with name and playerName", async () => {
      const mockResponse = { data: { session_id: "s1", player_id: "p1", player_token: "t1" } };
      mockedAxios.post.mockResolvedValueOnce(mockResponse);

      const result = await api.createSession("My Game", "Alice");

      expect(mockedAxios.post).toHaveBeenCalledWith(
        "/api/create-session",
        { name: "My Game", player_name: "Alice" }
      );
      expect(result.data.session_id).toBe("s1");
      expect(result.data.player_id).toBe("p1");
      expect(result.data.player_token).toBe("t1");
    });
  });

  describe("joinSession", () => {
    it("calls POST /api/join-session with session_id, player_name, and as_spectator", async () => {
      const mockResponse = { data: { session_id: "s2", player_id: "p2", player_token: "t2" } };
      mockedAxios.post.mockResolvedValueOnce(mockResponse);

      const result = await api.joinSession("s2", "Bob", false);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        "/api/join-session",
        { session_id: "s2", player_name: "Bob", as_spectator: false }
      );
      expect(result.data.session_id).toBe("s2");
    });

    it("returns the server-provided session_id (JoinSessionResponse.session_id)", async () => {
      // This tests that the response uses session_id from the server,
      // not from the input (important when joining via room code)
      const mockResponse = { data: { session_id: "actual-uuid-from-server", player_id: "p3", player_token: "t3" } };
      mockedAxios.post.mockResolvedValueOnce(mockResponse);

      const result = await api.joinSession("room-code", "Charlie", false);

      expect(result.data.session_id).toBe("actual-uuid-from-server");
    });

    it("passes as_spectator=true for spectator joins", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: { session_id: "s4", player_id: "p4", player_token: "t4" } });

      await api.joinSession("s4", "Dave", true);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        "/api/join-session",
        { session_id: "s4", player_name: "Dave", as_spectator: true }
      );
    });
  });

  describe("leaveSession", () => {
    it("exists and calls POST /api/leave-session with correct params", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: undefined });

      await api.leaveSession("s1", "p1", "t1");

      expect(mockedAxios.post).toHaveBeenCalledWith(
        "/api/leave-session",
        { session_id: "s1", player_id: "p1", player_token: "t1" }
      );
    });

    it("accepts three string parameters (sessionId, playerId, playerToken)", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: undefined });

      // Verify the function signature accepts exactly 3 args
      expect(api.leaveSession.length).toBe(3);
      await expect(api.leaveSession("a", "b", "c")).resolves.toBeDefined();
    });
  });

  describe("startGame", () => {
    it("calls POST /api/start-game", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: undefined });

      await api.startGame("s1");

      expect(mockedAxios.post).toHaveBeenCalledWith("/api/start-game", { session_id: "s1" });
    });
  });

  describe("startTestGame", () => {
    it("calls POST /api/start-test-game", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: undefined });

      await api.startTestGame("s1");

      expect(mockedAxios.post).toHaveBeenCalledWith("/api/start-test-game", { session_id: "s1" });
    });
  });

  describe("selectTeam", () => {
    it("calls POST /api/select-team with team members", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: undefined });

      await api.selectTeam("s1", "p1", "t1", ["p1", "p2", "p3"]);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        "/api/select-team",
        { session_id: "s1", player_id: "p1", player_token: "t1", team_members: ["p1", "p2", "p3"] }
      );
    });
  });

  describe("voteTeam", () => {
    it("calls POST /api/vote-team with vote boolean", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: undefined });

      await api.voteTeam("s1", "p1", "t1", true);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        "/api/vote-team",
        { session_id: "s1", player_id: "p1", player_token: "t1", vote: true }
      );
    });
  });

  describe("voteMission", () => {
    it("calls POST /api/vote-mission with vote boolean", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: undefined });

      await api.voteMission("s1", "p1", "t1", false);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        "/api/vote-mission",
        { session_id: "s1", player_id: "p1", player_token: "t1", vote: false }
      );
    });
  });

  describe("ladyOfLake", () => {
    it("calls POST /api/lady-of-lake and returns allegiance", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: { target_name: "Alice", allegiance: "good" } });

      const result = await api.ladyOfLake("s1", "p1", "t1", "p2");

      expect(mockedAxios.post).toHaveBeenCalledWith(
        "/api/lady-of-lake",
        { session_id: "s1", player_id: "p1", player_token: "t1", target_player_id: "p2" }
      );
      expect(result.data.allegiance).toBe("good");
    });
  });

  describe("assassinate", () => {
    it("calls POST /api/assassinate", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: undefined });

      await api.assassinate("s1", "p1", "t1", "p2");

      expect(mockedAxios.post).toHaveBeenCalledWith(
        "/api/assassinate",
        { session_id: "s1", player_id: "p1", player_token: "t1", target_player_id: "p2" }
      );
    });
  });

  describe("toggle settings", () => {
    it("toggleLadyOfLake calls correct endpoint", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: undefined });
      await api.toggleLadyOfLake("s1", true);
      expect(mockedAxios.post).toHaveBeenCalledWith("/api/toggle-lady-of-lake", { session_id: "s1", enabled: true });
    });

    it("toggleMordred calls correct endpoint", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: undefined });
      await api.toggleMordred("s1", false);
      expect(mockedAxios.post).toHaveBeenCalledWith("/api/toggle-mordred", { session_id: "s1", enabled: false });
    });

    it("toggleOberon calls correct endpoint", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: undefined });
      await api.toggleOberon("s1", true);
      expect(mockedAxios.post).toHaveBeenCalledWith("/api/toggle-oberon", { session_id: "s1", enabled: true });
    });
  });

  describe("restartGame", () => {
    it("calls POST /api/restart-game", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: undefined });
      await api.restartGame("s1");
      expect(mockedAxios.post).toHaveBeenCalledWith("/api/restart-game", { session_id: "s1" });
    });
  });

  describe("endGame", () => {
    it("calls POST /api/end-game", async () => {
      mockedAxios.post.mockResolvedValueOnce({ data: undefined });
      await api.endGame("s1");
      expect(mockedAxios.post).toHaveBeenCalledWith("/api/end-game", { session_id: "s1" });
    });
  });

  describe("getSession", () => {
    it("calls GET /api/session/:id", async () => {
      mockedAxios.get.mockResolvedValueOnce({ data: { id: "s1", name: "Game" } });

      const result = await api.getSession("s1");

      expect(mockedAxios.get).toHaveBeenCalledWith("/api/session/s1");
      expect(result.data.id).toBe("s1");
    });
  });

  describe("getSessionPersonalized", () => {
    it("calls GET /api/session/:id/me with query params", async () => {
      mockedAxios.get.mockResolvedValueOnce({ data: { type: "game_state", session: {} } });

      await api.getSessionPersonalized("s1", "p1", "t1");

      expect(mockedAxios.get).toHaveBeenCalledWith(
        "/api/session/s1/me",
        { params: { player_id: "p1", player_token: "t1" } }
      );
    });
  });
});
