export interface SharedConfig {
  enabled: boolean; version: 1; max_pickup_wait_s: number; max_shared_extra_ride_s: number;
  candidate_radius_m: number; preference_weights: { shared_only: number; exclusive_only: number };
  fare_factor?: number;
}
export const sharedDefaults = (): SharedConfig => ({ enabled: true, version: 1, max_pickup_wait_s: 600,
  max_shared_extra_ride_s: 450, candidate_radius_m: 500, preference_weights: { shared_only: 0, exclusive_only: 1 } });
export function sharedDraft(value: unknown): SharedConfig {
  const v = (value ?? {}) as Partial<SharedConfig>;
  return { ...sharedDefaults(), ...v, preference_weights: { ...sharedDefaults().preference_weights, ...v.preference_weights } };
}
export const minutesToSeconds = (minutes: number) => minutes * 60;
export const secondsToMinutes = (seconds: number) => seconds / 60;
export function validateShared(v: SharedConfig): void {
  const w = Object.values(v.preference_weights);
  if (v.version !== 1 || w.length !== 2 || w.some(x => !Number.isFinite(x) || x < 0) || !(w.reduce((a,b)=>a+b,0)>0))
    throw new Error("Tỷ lệ Shared Only / Exclusive Only phải hữu hạn, không âm và có tổng lớn hơn 0.");
  if (![v.max_pickup_wait_s,v.max_shared_extra_ride_s,v.candidate_radius_m].every(Number.isFinite) ||
      v.max_pickup_wait_s <= 0 || v.max_shared_extra_ride_s < 0 || v.candidate_radius_m <= 0)
    throw new Error("Hạn đón và bán kính phải lớn hơn 0; phần tăng thời gian trên xe không âm.");
}
