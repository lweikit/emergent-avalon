import { useState } from "react";
import api from "../../api";
import { LadyResult } from "../../types";
import { PhaseProps } from "./types";

export default function LadyOfTheLake({ session, currentPlayer, playerId, playerToken, execute, loading }: PhaseProps) {
  const [ladyTarget, setLadyTarget] = useState<string | null>(null);
  const [ladyResult, setLadyResult] = useState<LadyResult | null>(null);
  const [showLadyResult, setShowLadyResult] = useState(false);

  return (
    <div>
      {currentPlayer.lady_of_the_lake && (
        <div className="space-y-4">
          <p className="font-semibold text-yellow-300">Choose a player to reveal their allegiance:</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {session.players
              .filter((p) => p.id !== playerId && !p.is_spectator && !(session.lady_of_the_lake_previous_holders || []).includes(p.id))
              .map((player) => (
              <button key={player.id} onClick={() => setLadyTarget(player.id)}
                className={`p-2 sm:p-3 rounded-lg border-2 transition-colors text-sm ${ladyTarget === player.id ? "bg-yellow-600 text-white border-yellow-500" : "bg-gray-700 border-gray-600 text-gray-200 hover:border-yellow-400"}`}>
                {player.name}
              </button>
            ))}
          </div>
          {ladyTarget && (
            <div className="text-center">
              <button onClick={() => execute(async () => {
                const res = await api.ladyOfLake(session.id, playerId, playerToken, ladyTarget);
                setLadyResult(res.data);
                setShowLadyResult(true);
                setLadyTarget(null);
                setTimeout(() => setShowLadyResult(false), 10000);
              })}
                disabled={loading}
                className="bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-600 text-white font-bold py-2 px-6 rounded-lg transition-colors">
                {loading ? "Revealing..." : "Use Lady of the Lake"}
              </button>
            </div>
          )}
        </div>
      )}
      {ladyResult && showLadyResult && (
        <div className="mt-4 p-4 bg-yellow-900/30 border-2 border-yellow-500 rounded-lg shadow-lg text-center">
          <h4 className="text-lg font-bold text-yellow-300 mb-2">Lady of the Lake Reveals:</h4>
          <div className={`inline-block px-4 py-2 rounded-lg font-bold text-lg shadow-md ${ladyResult.allegiance === "good" ? "bg-blue-600 text-white" : "bg-red-600 text-white"}`}>
            {ladyResult.target_name} is {ladyResult.allegiance.toUpperCase()}
          </div>
        </div>
      )}
    </div>
  );
}
