"""Cấu hình V1 và lựa chọn dịch vụ với khóa CRN ổn định."""
from dataclasses import asdict, dataclass, field
import math

PREFERENCES = ("shared_only", "exclusive_only")
FARE_FACTOR = 0.7


@dataclass
class SharedRideConfig:
    enabled: bool = False
    version: int = 1
    max_pickup_wait_s: float = 600.0
    max_shared_extra_ride_s: float = 450.0
    candidate_radius_m: float = 500.0
    preference_weights: dict = field(default_factory=lambda: dict(shared_only=0.0, exclusive_only=1.0))

    def __post_init__(self):
        if type(self.enabled) is not bool or type(self.version) is not int or self.version != 1:
            raise ValueError("enabled phải là bool; version chỉ hỗ trợ 1")
        for key in ("max_pickup_wait_s", "max_shared_extra_ride_s", "candidate_radius_m"):
            x = getattr(self, key)
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
                raise ValueError(f"{key}: số phải hữu hạn")
            if x < 0 or (key != "max_shared_extra_ride_s" and x == 0):
                raise ValueError(f"{key}: giá trị ngoài giới hạn")
        w = self.preference_weights
        if not isinstance(w, dict) or set(w) - set(PREFERENCES):
            raise ValueError("preference_weights chỉ nhận shared_only / exclusive_only")
        vals = [w.get(k, 0.0) for k in PREFERENCES]
        if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) or x < 0 for x in vals):
            raise ValueError("preference_weights: trọng số hữu hạn, không âm")
        # Scale first to avoid overflowing the sum of finite large weights.
        scale = max(vals)
        if scale <= 0:
            raise ValueError("preference_weights: tổng phải > 0")
        total = sum(x / scale for x in vals)
        self.preference_weights = {k: (x / scale) / total for k, x in zip(PREFERENCES, vals)}

    def resolved(self):
        return dict(asdict(self), fare_factor=FARE_FACTOR)

    def preference(self, attrs, request_id, crn):
        explicit = attrs.get("service_preference")
        if explicit is not None:
            if explicit not in PREFERENCES:
                raise ValueError(f"requests[{request_id}].attrs.service_preference: lựa chọn không hợp lệ")
            return explicit
        return PREFERENCES[0] if crn.u("service_preference", request_id) < self.preference_weights[PREFERENCES[0]] else PREFERENCES[1]
