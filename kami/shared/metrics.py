"""Quan sát accumulator engine; chỉ đọc state, không phụ thuộc event log."""
from kami.core.agents import RiderState


def pair_actual(pair, t):
    ids = pair["rider_ids"]
    picks, drops = pair["pickups"], pair["dropoffs"]
    if not all(rid in picks for rid in ids):
        return dict(actual_shared=False, actual_overlap_s=0.0, overlap_start=None, overlap_end=None)
    start = max(picks[rid] for rid in ids)
    end = min(drops.get(rid, t) for rid in ids)
    overlap = max(0.0, end - start)
    return dict(actual_shared=overlap > 0, actual_overlap_s=overlap,
                overlap_start=start if overlap > 0 else None, overlap_end=end if overlap > 0 else None)


def compute(sim, riders, *, at=None):
    from kami.metrics import mean, percentile, ratio
    m = {f"shared.{k}": v for k, v in sim.shared_stats.items()}
    measured_ids = {r.id for r in riders}
    pairs = [p for p in sim.shared_pairs.values() if any(rid in measured_ids for rid in p["rider_ids"])]
    actual = [pair_actual(p, sim.t if at is None else at) for p in pairs]
    m.update({"shared.planned_pairs": len(pairs), "shared.actual_pairs": sum(p["actual_shared"] for p in actual),
              "shared.dissolved_pairs": sum(p["reason"] not in (None, "partner_cancelled_after_pickup") for p in pairs),
              "shared.overlap_min": sum(p["actual_overlap_s"] for p in actual) / 60,
              "shared.predicted_overlap_min": sum(p["predicted_overlap_s"] for p in pairs) / 60})
    for pref in ("shared_only", "exclusive_only"):
        rs = [r for r in riders if r.service_preference == pref]
        booked = [r for r in rs if r.t_booked is not None]
        done = [r for r in rs if r.state == RiderState.DONE]
        cancelled = [r for r in rs if r.state == RiderState.CANCELLED]
        picked = [r for r in rs if r.t_pickup is not None]
        waits = [(r.t_pickup-r.t_booked)/60 for r in picked]
        extras = [max(0, r.t_dropoff-r.t_pickup-r.shared_direct_baseline_s)/60 for r in done
                  if r.shared_direct_baseline_s is not None]
        predicted = [r.shared_predicted_extra_s/60 for r in rs if r.shared_predicted_extra_s is not None]
        gmv = sum(r.fare_paid for r in done)
        payout = sum(sim.fare_model.driver_payout(r.fare, r.surcharge) for r in done)
        vals = dict(requests=len(rs), booked=len(booked), served=len(done), cancelled=len(cancelled),
                    unfinished=sum(not r.is_terminal for r in booked), completion_rate=ratio(len(done), len(booked)),
                    cancel_rate=ratio(len(cancelled), len(booked)),
                    timeout=sum(r.cancellation_reason == "pickup_timeout" for r in cancelled),
                    no_pair=sum(not r.pair_history for r in cancelled) if pref == "shared_only" else 0,
                    wait_mean=mean(waits), wait_p50=percentile(waits,50), wait_p90=percentile(waits,90), wait_p95=percentile(waits,95),
                    extra_ride_mean=mean(extras), extra_ride_p90=percentile(extras,90), extra_ride_p95=percentile(extras,95),
                    predicted_extra_ride_mean=mean(predicted),
                    pickup_violations=sum(r.t_pickup > r.pickup_deadline+1e-9 for r in picked),
                    extra_ride_violations=sum(x*60 > sim.config.shared_ride.max_shared_extra_ride_s+1e-9 for x in extras) if pref == "shared_only" else 0,
                    gmv=gmv, payout=payout, platform_fee=gmv-payout,
                    reference_gmv=sum(r.exclusive_reference_fare for r in done),
                    savings=sum(r.exclusive_reference_fare-r.fare for r in done),
                    partner_lost_served=sum(sim.shared_pairs[r.pair_id]["reason"] == "partner_cancelled_after_pickup" for r in done if r.pair_id is not None))
        m.update({f"shared.{pref}.{k}": v for k,v in vals.items()})
    return m
