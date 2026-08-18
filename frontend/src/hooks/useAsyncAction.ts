import { useState, useCallback, useRef } from "react";
import { AxiosErrorResponse } from "../types";

export default function useAsyncAction() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  // A ref rather than the loading state: two clicks dispatched in the same tick
  // both read the same captured `loading` value and both used to get through.
  // The ref is also why `execute` can keep a stable identity.
  const inFlight = useRef(false);

  const execute = useCallback(async (fn: () => Promise<unknown>) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      const err = e as AxiosErrorResponse;
      setError(err.response?.data?.detail || "Action failed");
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  }, []);

  const clearError = useCallback(() => setError(""), []);

  return { execute, loading, error, clearError };
}
