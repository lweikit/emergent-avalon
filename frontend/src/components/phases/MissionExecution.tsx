import api from "../../api";
import { PhaseProps } from "./types";

export default function MissionExecution({ session, currentMission, playerId, playerToken, roleInfo, execute, loading }: PhaseProps) {
  if (!currentMission) return null;

  return (
    <div>
      <p className="mb-4 text-gray-300"><span className="font-bold text-orange-400">Mission Team:</span> {currentMission.team_members.map((id) => session.players.find((p) => p.id === id)?.name).filter(Boolean).join(", ")}</p>
      {currentMission.team_members.includes(playerId) && !currentMission.mission_votes?.player_voted && (
        <div>
          <p className="mb-4 font-semibold text-gray-200">You are on this mission! Choose your action:</p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button onClick={() => execute(() => api.voteMission(session.id, playerId, playerToken, true))}
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-bold py-3 px-6 rounded-lg transition-colors min-h-[48px]">
              Success
            </button>
            {roleInfo?.team === "evil" && (
              <button onClick={() => execute(() => api.voteMission(session.id, playerId, playerToken, false))}
                disabled={loading}
                className="bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white font-bold py-3 px-6 rounded-lg transition-colors min-h-[48px]">
                Fail
              </button>
            )}
          </div>
        </div>
      )}
      {currentMission.mission_votes && currentMission.mission_votes.total_votes > 0 && (
        <div className="mt-4 bg-gray-700 p-3 rounded-lg">
          <p className="text-sm text-gray-300">{currentMission.mission_votes.total_votes} of {currentMission.team_members.length} team members have voted</p>
        </div>
      )}
    </div>
  );
}
