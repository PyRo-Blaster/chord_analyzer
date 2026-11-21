"""jca-serve: run the API and its job worker with uvicorn."""

import argparse
import logging
import sys
from collections.abc import Sequence

import uvicorn

from jca_api.app import create_app
from jca_api.config import Settings

DEFAULT_HOST = "127.0.0.1"  # one user on one computer: not reachable from the network
DEFAULT_PORT = 8000


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jca-serve", description="Run the analyzer API.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    try:
        settings = Settings.from_env()
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    mode = "fake models" if settings.fake_pipeline else "real models"
    logging.getLogger(__name__).info("Data in %s, %s", settings.data_dir, mode)
    uvicorn.run(create_app(settings), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
