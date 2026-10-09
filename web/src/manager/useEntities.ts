"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Entity, Resource } from "./types";
export function useEntities<T>(kind: Resource) {
  const [items,setItems] = useState<Entity<T>[]>([]);
  const [error,setError] = useState<unknown>(null);
  const [loading,setLoading] = useState(true);
  const version = useRef(0), alive = useRef(true);
  const reload = useCallback(async () => {
    const v = ++version.current;
    setLoading(true);
    try { const result = await api.entities<T>(kind); if (alive.current && v === version.current) { setItems(result); setError(null); } }
    catch(e) { if (alive.current && v === version.current) setError(e); }
    finally { if (alive.current && v === version.current) setLoading(false); }
  },[kind]);
  useEffect(() => { alive.current = true; setLoading(true); void reload(); return () => { alive.current = false; version.current++; }; },[reload]);
  return { items, error, loading, reload };
}
