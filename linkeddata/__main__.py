"""The linked data of the platform.

    python -m linkeddata model                  generate the approved schema of the model
    python -m linkeddata import [--offline]     import every source (or its last download) into the database
    python -m linkeddata export                 write the records made on the platform to the records repository
    python -m linkeddata push                   send the records repository to its remote
    python -m linkeddata token ORCID NAME KIND  create a write token, for example the first one
"""

import argparse
import sys

from linkeddata import export, tokens
from linkeddata.imports import import_all
from linkeddata.model import write_schema


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m linkeddata", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["model", "import", "export", "push", "token"])
    parser.add_argument("arguments", nargs="*", help="token: the ORCID iD, the name, and the kinds it may write")
    parser.add_argument("--offline", action="store_true", help="import the sources downloaded by the last import")
    parser.add_argument("--days", type=int, default=tokens.DEFAULT_DAYS, help="how long a new token is valid")
    args = parser.parse_args()
    if args.command == "model":
        print(f"Wrote {write_schema()}")
    elif args.command == "import":
        problems = import_all(args.offline)
        for problem in problems:
            print(f"Not imported: {problem}", file=sys.stderr)
        if problems:
            sys.exit(1)
    elif args.command == "export":
        print("Exported" if export.export() else "Nothing changed")
    elif args.command == "push":
        export.push()
    else:
        if len(args.arguments) < 3:
            parser.error("token needs an ORCID iD, a name, and at least one kind")
        orcid, name, *kinds = args.arguments
        print(tokens.create(orcid, name, kinds, args.days))


if __name__ == "__main__":
    main()
