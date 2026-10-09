"""Thay đổi state shared thuộc engine; evaluator/dispatch chỉ đề xuất."""
from kami.core.agents import DriverState, RiderState
from kami.core.events import EventType as E
from kami.behavior.protocols import TripOffer


class SharedLifecycle:
    def _shared_info(self, r):
        if not self.shared_enabled:
            return {}
        return dict(service_preference=r.service_preference, effective_mode=r.effective_mode,
                    pair_id=r.pair_id, pickup_deadline=r.pickup_deadline,
                    exclusive_reference_fare=r.exclusive_reference_fare)

    def _offer_shared_plan(self, driver, riders, ev):
        if not driver.available or any(r.state != RiderState.WAITING or r.job_id not in self.open_jobs for r in riders):
            return False
        key = (driver.id, *sorted(r.id for r in riders))
        attempts = self.shared_offers.get(key, 0) + 1
        self.shared_offers[key] = attempts
        fare = sum(r.fare for r in riders)
        offer = TripOffer(min(ev.pickup_t.values()) - self.t, self.fare_model.driver_payout(fare),
                          ev.total_dist_m, self.zones.zone_of(ev.stops[-1].loc), False,
                          shared=len(riders) == 2, rider_ids=tuple(sorted(r.id for r in riders)))
        driver.offers += 1
        p = self.behavior.suite.driver_accept.p_accept(driver, offer, self.context(self.current_loc(driver)))
        self.log.add(self.t, E.TRIP_OFFERED, riders[0].id, driver.id,
                     shared=offer.shared, riders=list(offer.rider_ids), fare=offer.fare, p=p)
        if self.crn.u("shared_driver_accept", *key, attempts) >= p:
            driver.rejections += 1
            if len(riders) == 1:
                self.jobs[riders[0].job_id].tabu.add(driver.id)
            self.log.add(self.t, E.TRIP_REJECTED, riders[0].id, driver.id, shared=offer.shared)
            return False
        # Recheck after behavior returns, before any mutation.
        if not driver.available or any(r.state != RiderState.WAITING or self.t > r.pickup_deadline for r in riders):
            return False
        self._interrupt_leg(driver)
        for r in riders:
            old = self.open_jobs.pop(r.job_id)
            if len(riders) == 2:
                old.rider_ids = []
        if len(riders) == 2:
            job = self._new_job([r.id for r in riders], stops=ev.stops)
            pair_id = len(self.shared_pairs) + 1
            job.pair_id = pair_id
            pair = dict(id=pair_id, rider_ids=list(offer.rider_ids), driver_id=driver.id, created_t=self.t,
                        closed_t=None, reason=None,
                        stops=[dict(kind=s.kind, rider_id=s.rider_id, loc=s.loc) for s in ev.stops],
                        predicted_pickup=ev.pickup_t, predicted_dropoff=ev.dropoff_t,
                        direct_baseline_s=ev.direct_baseline_s, predicted_extra_s=ev.extra_ride_s,
                        predicted_overlap_s=ev.overlap_s, pickups={}, dropoffs={})
            self.shared_pairs[pair_id] = pair
            self.log.add(self.t, "SHARED_PAIR_CREATED", None, driver.id, pair_id=pair_id,
                         rider_ids=list(offer.rider_ids), stops=pair["stops"],
                         predicted_pickup=dict(ev.pickup_t), predicted_dropoff=dict(ev.dropoff_t),
                         direct_baseline_s=dict(ev.direct_baseline_s), predicted_extra_s=dict(ev.extra_ride_s),
                         predicted_overlap_s=ev.overlap_s)
        else:
            job = self.jobs[riders[0].job_id]
        job.driver_id, job.stops = driver.id, list(ev.stops)
        driver.job_ids.append(job.id)
        driver.plan = list(ev.stops)
        for r in riders:
            r.job_id = job.id
            r.pair_id = job.pair_id
            if job.pair_id is not None:
                r.pair_history.append(job.pair_id)
            r.shared_direct_baseline_s = ev.direct_baseline_s[r.id]
            r.shared_predicted_extra_s = ev.extra_ride_s[r.id]
            r.effective_mode = "shared" if len(riders) == 2 else "exclusive"
            r.state, r.driver_id, r.t_matched = RiderState.MATCHED, driver.id, self.t
            r.version += 1
            r.eta_promised = ev.pickup_t[r.id]
            self._arm_cancel(r, "matched")
            self.log.add(self.t, E.TRIP_ACCEPTED, r.id, driver.id, job=job.id,
                         eta=r.eta_promised-self.t, predicted_extra_s=ev.extra_ride_s[r.id],
                         direct_baseline_s=ev.direct_baseline_s[r.id], **self._shared_info(r))
        self._set_driver_state(driver, DriverState.EN_ROUTE)
        self._start_next_leg(driver)
        return True

    def _on_pickup_deadline(self, rider_id, deadline):
        r = self.riders[rider_id]
        if r.pickup_deadline != deadline or r.state not in (RiderState.WAITING, RiderState.MATCHED):
            return
        self._cancel_shared(r, "pickup_timeout")

    def _cancel_shared(self, r, reason):
        if r.state not in (RiderState.WAITING, RiderState.MATCHED):
            return
        self._accrue(r)
        phase = "waiting" if r.state == RiderState.WAITING else "matched"
        r.state, r.t_cancel, r.cancel_phase = RiderState.CANCELLED, self.t, phase
        r.cancellation_reason = reason
        r.version += 1
        r.cancel_token += 1
        job = self.jobs[r.job_id]
        job.rider_ids = [rid for rid in job.rider_ids if rid != r.id]
        job.stops = [s for s in job.stops if s.rider_id != r.id]
        if job.driver_id is None:
            self.open_jobs.pop(job.id, None)
        else:
            d = self.drivers[job.driver_id]
            depart = max(self.t, d.leg.t_depart) if d.leg else self.t
            self._interrupt_leg(d)
            pair = self.shared_pairs.get(job.pair_id)
            if pair is not None and not d.onboard:
                pair["closed_t"], pair["reason"] = self.t, reason
                self.log.add(self.t, "SHARED_PAIR_DISSOLVED", r.id, d.id, pair_id=pair["id"], reason=reason)
                for rid in job.rider_ids:
                    survivor = self.riders[rid]
                    if survivor.state != RiderState.MATCHED:
                        continue
                    survivor.state = RiderState.WAITING
                    survivor.version += 1
                    survivor.driver_id, survivor.pair_id, survivor.effective_mode = None, None, None
                    new = self._new_job([rid])
                    survivor.job_id = new.id
                    self.open_jobs[new.id] = new
                    self._arm_cancel(survivor, "waiting")
                    self.log.add(self.t, "SHARED_REQUEUED", rid, None, old_pair_id=pair["id"],
                                 booked_t=survivor.t_booked, **self._shared_info(survivor))
                job.rider_ids, job.stops = [], []
                d.plan = []
                self._become_idle(d)
            else:
                d.plan = [s for s in d.plan if s.rider_id != r.id]
                if pair is not None:
                    pair["reason"] = "partner_cancelled_after_pickup"
                    self.log.add(self.t, "SHARED_PARTNER_LOST", r.id, d.id, pair_id=pair["id"], reason=reason)
                self._start_next_leg(d, depart_at=depart)
        self.log.add(self.t, E.RIDER_CANCEL, r.id, r.driver_id, phase=phase, reason=reason,
                     waited=self.t-r.t_booked, **self._shared_info(r))
        self.policy.on_rider_cancel(self, r)

    def _shared_pickup(self, r):
        if r.pair_id is not None:
            self.shared_pairs[r.pair_id]["pickups"][r.id] = self.t

    def _shared_dropoff(self, r):
        if r.pair_id is not None:
            pair = self.shared_pairs[r.pair_id]
            pair["dropoffs"][r.id] = self.t
            if all(self.riders[rid].is_terminal for rid in pair["rider_ids"]):
                pair["closed_t"] = self.t
                self.log.add(self.t, "SHARED_PAIR_FINISHED", None, pair["driver_id"], pair_id=pair["id"])
