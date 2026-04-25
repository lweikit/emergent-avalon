import { useState } from "react";
import api from "../../api";
import { PhaseProps } from "./types";

export default function Assassination({ session, playerId, playerToken, roleInfo, execute, loading }: PhaseProps) {
  const [assassinTarget, setAssassinTarget] = useState("");

  if (roleInfo?.role !== "assassin") {
    return <p className="text-center text-sm text-gray-400">The Assassin is choosing their target...</p>;
  }

  return (
    <div className="space-y-4">
      <p className="font-semibold text-red-400">Good has won the missions, but you can assassinate Merlin!</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {session.players.filter((p) => p.id !== playerId && !p.is_spectator).map((player) => (
          <button key={player.id} onClick={() => setAssassinTarget(player.id)}
            className={`p-2 sm:p-3 rounded-lg border-2 transition-colors text-sm ${assassinTarget === player.id ? "bg-red-600 text-white border-red-500" : "bg-gray-700 border-gray-600 text-gray-200 hover:border-red-400"}`}>
            {player.name}
          </button>
        ))}
      </div>
      {assassinTarget && (
        <div className="text-center">
          <button onClick={() => execute(async () => { await api.assassinate(session.id, playerId, playerToken, assassinTarget); setAssassinTarget(""); })}
            disabled={loading}
            className="bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white font-bold py-2 px-6 rounded-lg transition-colors">
            {loading ? "Assassinating..." : `Assassinate ${session.players.find((p) => p.id === assassinTarget)?.name}`}
          </button>
        </div>
      )}
    </div>
  );
}
