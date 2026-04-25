import { GameState, Mission, Player, RoleInfo } from "../../types";

export interface PhaseProps {
  session: GameState["session"];
  currentMission: Mission | null;
  currentPlayer: Player;
  currentLeader: Player | undefined;
  playerId: string;
  playerToken: string;
  roleInfo?: RoleInfo;
  selectedTeam: string[];
  setSelectedTeam: (team: string[]) => void;
  execute: (fn: () => Promise<unknown>) => Promise<void>;
  loading: boolean;
}
