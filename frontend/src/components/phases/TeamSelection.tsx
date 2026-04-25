import api from "../../api";
import { PhaseProps } from "./types";

export default function TeamSelection({ session, currentMission, currentPlayer, currentLeader, playerId, playerToken, selectedTeam, setSelectedTeam, execute, loading }: PhaseProps) {
  if (!currentMission) return null;

  const toggleTeamMember = (id: string) => {
    if (selectedTeam.includes(id)) {
      setSelectedTeam(selectedTeam.filter((x) => x !== id));
    } else if (selectedTeam.length < currentMission.team_size) {
      setSelectedTeam([...selectedTeam, id]);
    }
  };

  return (
    <div>
      <p className="mb-4 text-gray-300"><span className="text-yellow-400 font-bold">{currentLeader?.name}</span> must select {currentMission.team_size} players</p>
      {currentPlayer.is_leader && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {session.players.filter((p) => !p.is_spectator).map((player) => (
              <button key={player.id} onClick={() => toggleTeamMember(player.id)}
                className={`p-2 sm:p-3 rounded-lg border-2 transition-colors text-sm ${selectedTeam.includes(player.id) ? "bg-blue-600 text-white border-blue-500" : "bg-gray-700 border-gray-600 text-gray-200 hover:border-blue-400"}`}>
                {player.name}
              </button>
            ))}
          </div>
          <div className="text-center">
            <p className="mb-2 text-gray-300">Selected: {selectedTeam.length}/{currentMission.team_size}</p>
            <button onClick={() => execute(async () => { await api.selectTeam(session.id, playerId, playerToken, selectedTeam); setSelectedTeam([]); })}
              disabled={selectedTeam.length !== currentMission.team_size || loading}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-bold py-2 px-6 rounded-lg transition-colors">
              {loading ? "Proposing..." : "Propose Team"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
