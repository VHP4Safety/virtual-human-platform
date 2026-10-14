"""The linked data of the platform.

    python -m linkeddata model                  generate the approved schema of the model
    python -m linkeddata build [--offline]      fetch (or reuse) the sources and build the pages
    python -m linkeddata push                   send the records repository to its remote
    python -m linkeddata token ORCID NAME KIND  create a write token, for example the first one
"""

import argparse
from pathlib import Path

from linkeddata import records, tokens
from linkeddata.build import build
from linkeddata.model import write_schema


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m linkeddata", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["model", "build", "push", "token"])
    parser.add_argument("arguments", nargs="*", help="token: the ORCID iD, the name, and the kinds it may write")
    parser.add_argument("--out", type=Path, default=Path("build"), help="folder for the built files")
    parser.add_argument("--offline", action="store_true", help="reuse the sources downloaded by the last build")
    parser.add_argument("--days", type=int, default=tokens.DEFAULT_DAYS, help="how long a new token is valid")
    args = parser.parse_args()
    if args.command == "model":
        print(f"Wrote {write_schema()}")
    elif args.command == "build":
        database = build(args.out, args.offline)
        print(f"Wrote {database}" if database else "Another build is running; it builds this change too.")
    elif args.command == "push":
        records.push()
    else:
        if len(args.arguments) < 3:
            parser.error("token needs an ORCID iD, a name, and at least one kind")
        orcid, name, *kinds = args.arguments
        print(tokens.create(orcid, name, kinds, args.days))


if __name__ == "__main__":
    main()
