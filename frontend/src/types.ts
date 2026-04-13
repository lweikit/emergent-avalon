export interface Player {
  id: string;
  name: string;
  role: string | null;
  is_leader: boolean;
  is_connected: boolean;
  lady_of_the_lake: boolean;
  is_bot: boolean;
  is_spectator: boolean;
}

export interface MissionVotes {
  player_voted?: boolean;
  total_votes: number;
  fail_count?: number;
  success_count?: number;
}

export interface Mission {
  number: number;
  team_size: number;
  fails_required: number;
  team_members: string[];
  votes: Record<string, boolean>;
  mission_votes: MissionVotes | null;
  result: string;
  team_approved: boolean | null;
}

export interface VoteRecord {
  mission: number;
  result: string;
  approve_count: number;
  total_votes: number;
  votes: Record<string, boolean>;
}

export interface Session {
  id: string;
  name: string;
  phase: string;
  current_mission: number;
  current_leader: number;
  vote_track: number;
  good_wins: number;
  evil_wins: number;
  game_result: string | null;
  lady_of_the_lake_enabled: boolean;
  lady_of_the_lake_previous_holders: string[];
  mordred_enabled: boolean;
  oberon_enabled: boolean;
  players: Player[];
  missions: Mission[];
  vote_history: VoteRecord[];
  game_log: string[];
}

export interface RoleVisiblePlayer {
  name: string;
  role: string;
}

export interface RoleInfo {
  role: string;
  team: string;
  description: string;
  sees: RoleVisiblePlayer[];
}

export interface LadyResult {
  target_name: string;
  allegiance: string;
}

export interface GameState {
  type: string;
  session: Session;
  role_info?: RoleInfo;
  lady_of_lake_knowledge?: LadyResult[];
  current_mission_details?: Mission;
}
