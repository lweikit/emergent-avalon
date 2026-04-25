import { useState, useCallback } from "react";
import { AxiosErrorResponse } from "../types";

export default function useAsyncAction() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const execute = useCallback(async (fn: () => Promise<unknown>) => {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      const err = e as AxiosErrorResponse;
      setError(err.response?.data?.detail || "Action failed");
    } finally {
      setLoading(false);
    }
  }, [loading]);

  const clearError = useCallback(() => setError(""), []);

  return { execute, loading, error, clearError };
}
