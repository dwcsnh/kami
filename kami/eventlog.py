"""Event log: every processed event and platform action, in processing order.

Rows are plain tuples for speed. Export to CSV / JSONL with the standard
library, to a pandas DataFrame if pandas is installed, and to Parquet if
pyarrow is installed (design doc §12 suggests Parquet for event logs).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

Row = Tuple[float, str, Optional[int], Optional[int], Dict[str, Any]]

COLUMNS = ("t", "event", "rider_id", "driver_id", "info")


class EventLog:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.rows: List[Row] = []

    def add(self, t: float, event: str, rider_id: Optional[int] = None, driver_id: Optional[int] = None,
            **info: Any) -> None:
        if self.enabled:
            self.rows.append((round(t, 3), str(event.value if hasattr(event, "value") else event), rider_id,
                              driver_id, info))

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[Row]:
        return iter(self.rows)

    def filter(self, event: Optional[str] = None, rider_id: Optional[int] = None,
               driver_id: Optional[int] = None) -> List[Row]:
        return [r for r in self.rows if (event is None or r[1] == event) and
                (rider_id is None or r[2] == rider_id) and (driver_id is None or r[3] == driver_id)]

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for r in self.rows:
            out[r[1]] = out.get(r[1], 0) + 1
        return out

    def to_csv(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS)
            for t, ev, r, d, info in self.rows:
                w.writerow([t, ev, "" if r is None else r, "" if d is None else d,
                            json.dumps(info, default=str, ensure_ascii=False)])
        return path

    def to_jsonl(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for t, ev, r, d, info in self.rows:
                f.write(json.dumps({"t": t, "event": ev, "rider_id": r, "driver_id": d, **info},
                                   default=str, ensure_ascii=False) + "\n")
        return path

    def to_pandas(self):
        import pandas as pd

        return pd.DataFrame([{"t": t, "event": ev, "rider_id": r, "driver_id": d, **info}
                             for t, ev, r, d, info in self.rows])

    def to_parquet(self, path: str | Path) -> Path:
        df = self.to_pandas()
        df.to_parquet(path)  # needs pyarrow or fastparquet
        return Path(path)
