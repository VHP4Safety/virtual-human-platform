"""The linked data of the platform.

    python -m linkeddata model                  generate the approved schema of the model
    python -m linkeddata build [--offline]      fetch (or reuse) the sources and build the pages
    python -m linkeddata push                   send the records repository to its remote
"""

import argparse
from pathlib import Path

from linkeddata import records
from linkeddata.build import build
from linkeddata.model import write_schema


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m linkeddata", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["model", "build", "push"])
    parser.add_argument("--out", type=Path, default=Path("build"), help="folder for the built files")
    parser.add_argument("--offline", action="store_true", help="reuse the sources downloaded by the last build")
    args = parser.parse_args()
    if args.command == "model":
        print(f"Wrote {write_schema()}")
    elif args.command == "build":
        database = build(args.out, args.offline)
        print(f"Wrote {database}" if database else "Another build is running; it builds this change too.")
    else:
        records.push()


if __name__ == "__main__":
    main()
