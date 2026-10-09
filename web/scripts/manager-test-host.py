"""Test-only HTTP host; uses an isolated SQLite file and real spawned workers."""
import argparse
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import uvicorn
from kami.service import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--artifacts", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--stop-file", required=True)
    args = parser.parse_args()
    server = uvicorn.Server(uvicorn.Config(
        create_app(args.db, args.artifacts, interval_s=0.01),
        host="127.0.0.1", port=args.port, log_level="warning",
    ))

    def control():
        while not Path(args.stop_file).exists():
            time.sleep(0.1)
        server.should_exit = True

    threading.Thread(target=control, daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
