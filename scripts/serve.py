"""Start the dashboard.

Usage:
    .venv/bin/python scripts/serve.py              # this computer only: http://127.0.0.1:8000
    .venv/bin/python scripts/serve.py --lan        # also reachable from your home network

The page has no login, so --lan is only for a trusted home network.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import uvicorn  # noqa: E402

from training_agent.web.app import create_app  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lan", action="store_true", help="listen on all network interfaces")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(create_app(), host="0.0.0.0" if args.lan else "127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
