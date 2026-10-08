"""``python -m kami.osm {fetch,build,check} <config>`` — see ``kami.osm``."""
from __future__ import annotations

import argparse
import json
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m kami.osm", description="OSM → kami road network pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download the source PBF of a build config and check its sha256")
    f.add_argument("config", help="config name under data/osm (e.g. hanoi) or JSON path")
    b = sub.add_parser("build", help="build the network and zone systems of a config")
    b.add_argument("config")
    b.add_argument("--data-root", default=None, help="output data folder (default: $KAMI_DATA_ROOT or <repo>/data)")
    c = sub.add_parser("check", help="routing check / benchmark of a built network (S02-2)")
    c.add_argument("network", help="network name under <data_root>/networks or folder")
    c.add_argument("--pairs", type=int, default=1000)
    c.add_argument("--seed", type=int, default=0)
    c.add_argument("--python-pairs", type=int, default=200, help="pairs compared with the pure-Python router")
    c.add_argument("--data-root", default=None)
    c.add_argument("--out", default=None, help="write the results JSON here")
    args = ap.parse_args(argv)

    if args.cmd in ("fetch", "build"):
        from kami.osm import build, fetch, load_config

        cfg = load_config(args.config)
        if args.cmd == "fetch":
            print(fetch(cfg))
            return 0
        build(cfg, args.data_root)
        return 0
    from kami.osm.check import check

    res = check(args.network, n_pairs=args.pairs, seed=args.seed, python_pairs=args.python_pairs,
                data_root=args.data_root)
    text = json.dumps(res, indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
