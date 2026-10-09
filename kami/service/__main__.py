"""python -m kami.service: local, single-supervisor HTTP service."""
import argparse
from kami.service import create_app


def main(argv=None):
    parser = argparse.ArgumentParser(description="kami backend service (giai đoạn A)")
    parser.add_argument("--db", default="kami.db")
    parser.add_argument("--artifacts", default="runs")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--interval-s", type=float, default=0.25)
    args = parser.parse_args(argv)
    try:
        import uvicorn
        app = create_app(args.db, args.artifacts, args.interval_s)
    except ImportError:
        parser.error("cài backend bằng pip install 'kami[service]'")
    uvicorn.run(app, host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
