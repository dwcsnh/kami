"""Event log: every processed event and platform action, in processing order.

Rows are plain tuples for speed. Export to CSV / JSONL with the standard
library, to a pandas DataFrame if pandas is installed, and to Parquet if
pyarrow is installed (design doc §12 suggests Parquet for event logs).

``save`` / ``load`` write and read the run artifact format (sprint 01): Parquet
(``pyarrow``) or gzip-compressed CSV, columns ``t, event, rider_id, driver_id,
info`` with ``info`` as a JSON string. Listeners (``subscribe``) see every row,
even when recording is off (time-series sampler, live streaming).
"""
from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

Row = Tuple[float, str, Optional[int], Optional[int], Dict[str, Any]]

COLUMNS = ("t", "event", "rider_id", "driver_id", "info")
FORMATS = ("parquet", "csv.gz")
Listener = Callable[[float, str, Optional[int], Optional[int], Dict[str, Any]], None]
PARQUET_HINT = "Parquet event logs need pyarrow: pip install 'kami[store]' (or use the csv.gz format)"


class EventLog:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.rows: List[Row] = []
        self._listeners: List[Listener] = []

    def subscribe(self, fn: Listener) -> None:
        """Call ``fn(t, event, rider_id, driver_id, info)`` for every row, also when recording is off."""
        self._listeners.append(fn)

    def add(self, t: float, event: str, rider_id: Optional[int] = None, driver_id: Optional[int] = None,
            **info: Any) -> None:
        if self.enabled or self._listeners:
            ev = str(event.value if hasattr(event, "value") else event)
            if self.enabled:
                self.rows.append((round(t, 3), ev, rider_id, driver_id, info))
            for fn in self._listeners:
                fn(t, ev, rider_id, driver_id, info)

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

    def to_csv(self, path: str | Path, compress: Optional[bool] = None) -> Path:
        """CSV with ``info`` as JSON; gzip-compressed when ``compress`` (default: path ends with ``.gz``)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if compress is None:
            compress = path.suffix == ".gz"
        opener = gzip.open if compress else open
        with opener(path, "wt", newline="") as f:
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

    def save(self, path: str | Path, fmt: str = "parquet", batch_rows: int = 100_000) -> Path:
        """Write the run artifact: ``fmt`` = ``"parquet"`` (needs pyarrow) or ``"csv.gz"``."""
        if fmt == "csv.gz":
            return self.to_csv(path, compress=True)
        if fmt != "parquet":
            raise ValueError(f"unknown event log format {fmt!r}; expected one of {FORMATS}")
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as e:  # pragma: no cover - depends on the environment
            raise ImportError(PARQUET_HINT) from e
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        schema = pa.schema([("t", pa.float64()), ("event", pa.string()), ("rider_id", pa.int64()),
                            ("driver_id", pa.int64()), ("info", pa.string())])
        with pq.ParquetWriter(str(path), schema, compression="zstd") as w:
            for k in range(0, max(len(self.rows), 1), batch_rows):
                chunk = self.rows[k:k + batch_rows]
                cols = list(zip(*chunk)) if chunk else [()] * 5
                w.write_table(pa.table({
                    "t": pa.array(cols[0], pa.float64()), "event": pa.array(cols[1], pa.string()),
                    "rider_id": pa.array(cols[2], pa.int64()), "driver_id": pa.array(cols[3], pa.int64()),
                    "info": pa.array([json.dumps(i, default=str, ensure_ascii=False) for i in cols[4]], pa.string()),
                }, schema=schema))
        return path


def load(path: str | Path) -> List[Row]:
    """Read an event log written by ``EventLog.save`` / ``to_csv`` (``.parquet``, ``.csv.gz`` or ``.csv``)."""
    path = Path(path)
    if path.suffix == ".parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as e:  # pragma: no cover
            raise ImportError(PARQUET_HINT) from e
        d = pq.read_table(str(path)).to_pydict()
        return [(t, ev, r, dr, json.loads(i)) for t, ev, r, dr, i in
                zip(d["t"], d["event"], d["rider_id"], d["driver_id"], d["info"])]
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="") as f:
        return [(float(row["t"]), row["event"], int(row["rider_id"]) if row["rider_id"] else None,
                 int(row["driver_id"]) if row["driver_id"] else None, json.loads(row["info"]))
                for row in csv.DictReader(f)]
