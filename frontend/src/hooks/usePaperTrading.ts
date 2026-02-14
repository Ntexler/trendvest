"use client";
import { useState, useEffect, useCallback } from "react";
import { getSessionId } from "@/lib/api";

export function usePaperTrading() {
  const [sessionId, setSessionId] = useState("");

  useEffect(() => {
    setSessionId(getSessionId());
  }, []);

  return { sessionId };
}
