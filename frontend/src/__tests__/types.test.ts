import { GamePhase } from "../types";
import type { Player, Session, Mission, MissionVotes, VoteRecord, RoleInfo, RoleVisiblePlayer, LadyResult, GameState } from "../types";

describe("GamePhase", () => {
  it("has all expected phase values", () => {
    expect(GamePhase.LOBBY).toBe("lobby");
    expect(GamePhase.ROLE_ASSIGNMENT).toBe("role_assignment");
    expect(GamePhase.MISSION_TEAM_SELECTION).toBe("mission_team_selection");
    expect(GamePhase.MISSION_VOTING).toBe("mission_voting");
    expect(GamePhase.VOTE_REVEAL).toBe("vote_reveal");
    expect(GamePhase.MISSION_EXECUTION).toBe("mission_execution");
    expect(GamePhase.MISSION_REVEAL).toBe("mission_reveal");
    expect(GamePhase.LADY_OF_THE_LAKE).toBe("lady_of_the_lake");
    expect(GamePhase.ASSASSINATION).toBe("assassination");
    expect(GamePhase.GAME_END).toBe("game_end");
  });

  it("contains exactly 10 phases", () => {
    const keys = Object.keys(GamePhase);
    expect(keys).toHaveLength(10);
  });

  it("is a const object (values are readonly)", () => {
    // Verify each key maps to the expected snake_case string
    const expectedEntries: [string, string][] = [
      ["LOBBY", "lobby"],
      ["ROLE_ASSIGNMENT", "role_assignment"],
      ["MISSION_TEAM_SELECTION", "mission_team_selection"],
      ["MISSION_VOTING", "mission_voting"],
      ["VOTE_REVEAL", "vote_reveal"],
      ["MISSION_EXECUTION", "mission_execution"],
      ["MISSION_REVEAL", "mission_reveal"],
      ["LADY_OF_THE_LAKE", "lady_of_the_lake"],
      ["ASSASSINATION", "assassination"],
      ["GAME_END", "game_end"],
    ];
    expect(Object.entries(GamePhase)).toEqual(expectedEntries);
  });
});

describe("Interface contracts (compile-time type checks at runtime)", () => {
  it("Player interface has the expected shape", () => {
    const player: Player = {
      id: "p1",
      name: "Alice",
      role: null,
      is_leader: false,
      is_connected: true,
      lady_of_the_lake: false,
      is_bot: false,
      is_spectator: false,
    };
    expect(player.id).toBe("p1");
    expect(player.name).toBe("Alice");
    expect(player.role).toBeNull();
    expect(player.is_leader).toBe(false);
    expect(player.is_connected).toBe(true);
    expect(player.lady_of_the_lake).toBe(false);
    expect(player.is_bot).toBe(false);
    expect(player.is_spectator).toBe(false);
  });

  it("Player.role can be a string or null", () => {
    const withRole: Player = {
      id: "p2",
      name: "Bob",
      role: "merlin",
      is_leader: true,
      is_connected: true,
      lady_of_the_lake: false,
      is_bot: false,
      is_spectator: false,
    };
    expect(withRole.role).toBe("merlin");

    const withoutRole: Player = {
      id: "p3",
      name: "Carol",
      role: null,
      is_leader: false,
      is_connected: false,
      lady_of_the_lake: false,
      is_bot: true,
      is_spectator: false,
    };
    expect(withoutRole.role).toBeNull();
  });

  it("MissionVotes interface works with optional fields", () => {
    const minimal: MissionVotes = { total_votes: 3 };
    expect(minimal.total_votes).toBe(3);
    expect(minimal.player_voted).toBeUndefined();
    expect(minimal.fail_count).toBeUndefined();
    expect(minimal.success_count).toBeUndefined();

    const full: MissionVotes = {
      player_voted: true,
      total_votes: 5,
      fail_count: 2,
      success_count: 3,
    };
    expect(full.player_voted).toBe(true);
    expect(full.fail_count).toBe(2);
    expect(full.success_count).toBe(3);
  });

  it("Mission interface has the expected shape", () => {
    const mission: Mission = {
      number: 1,
      team_size: 3,
      fails_required: 1,
      team_members: ["p1", "p2", "p3"],
      votes: { p1: true, p2: false },
      mission_votes: null,
      result: "pending",
      team_approved: null,
    };
    expect(mission.number).toBe(1);
    expect(mission.team_size).toBe(3);
    expect(mission.team_members).toHaveLength(3);
    expect(mission.mission_votes).toBeNull();
    expect(mission.team_approved).toBeNull();
  });

  it("Session interface includes code field (optional/nullable)", () => {
    const session: Session = {
      id: "sess-1",
      name: "Test Game",
      code: "ABC123",
      phase: GamePhase.LOBBY,
      current_mission: 0,
      current_leader: 0,
      vote_track: 0,
      good_wins: 0,
      evil_wins: 0,
      game_result: null,
      lady_of_the_lake_enabled: false,
      lady_of_the_lake_previous_holders: [],
      mordred_enabled: false,
      oberon_enabled: false,
      players: [],
      missions: [],
      vote_history: [],
      game_log: [],
    };
    expect(session.code).toBe("ABC123");

    const noCode: Session = { ...session, code: null };
    expect(noCode.code).toBeNull();

    const undefinedCode: Session = { ...session, code: undefined };
    expect(undefinedCode.code).toBeUndefined();
  });

  it("RoleInfo and RoleVisiblePlayer interfaces work", () => {
    const visiblePlayer: RoleVisiblePlayer = {
      name: "Alice",
      role: "morgana",
    };
    const roleInfo: RoleInfo = {
      role: "merlin",
      team: "good",
      description: "Knows evil players",
      sees: [visiblePlayer],
    };
    expect(roleInfo.role).toBe("merlin");
    expect(roleInfo.sees).toHaveLength(1);
    expect(roleInfo.sees[0].name).toBe("Alice");
  });

  it("LadyResult interface works", () => {
    const result: LadyResult = {
      target_name: "Alice",
      allegiance: "good",
    };
    expect(result.target_name).toBe("Alice");
    expect(result.allegiance).toBe("good");
  });

  it("GameState interface has required and optional fields", () => {
    const gameState: GameState = {
      type: "game_state",
      session: {
        id: "s1",
        name: "Game",
        phase: GamePhase.LOBBY,
        current_mission: 0,
        current_leader: 0,
        vote_track: 0,
        good_wins: 0,
        evil_wins: 0,
        game_result: null,
        lady_of_the_lake_enabled: false,
        lady_of_the_lake_previous_holders: [],
        mordred_enabled: false,
        oberon_enabled: false,
        players: [],
        missions: [],
        vote_history: [],
        game_log: [],
      },
    };
    expect(gameState.type).toBe("game_state");
    expect(gameState.role_info).toBeUndefined();
    expect(gameState.lady_of_lake_knowledge).toBeUndefined();
    expect(gameState.current_mission_details).toBeUndefined();
  });
});
