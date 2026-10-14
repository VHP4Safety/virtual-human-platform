"""The linked data of the platform: python -m linkeddata model, or python -m linkeddata build."""

import argparse
from pathlib import Path

from linkeddata.build import build
from linkeddata.model import write_schema


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m linkeddata", description=__doc__)
    parser.add_argument(
        "command",
        choices=["model", "build"],
        help="model: generate the approved schema of the model; build: fetch and map all sources into SQLite",
    )
    parser.add_argument("--out", type=Path, default=Path("build"), help="folder for the built database")
    args = parser.parse_args()
    if args.command == "model":
        print(f"Wrote {write_schema()}")
    else:
        print(f"Wrote {build(args.out)}")


if __name__ == "__main__":
    main()
