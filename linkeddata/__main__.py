"""The linked data of the platform.

    python -m linkeddata model                  generate the approved schema of the model and its tables
    python -m linkeddata check                  check that the generated files, the vocabularies and the
                                                database are those of the model's release
    python -m linkeddata import                 import every source into the database
    python -m linkeddata export                 write the records made on the platform to the records repository
    python -m linkeddata push                   send the records repository to its remote
    python -m linkeddata backup                 copy the database to PLATFORM_STATE/backups (the latest 14 are kept)
    python -m linkeddata token ORCID NAME KIND  create a write token, for example the first one
"""

import argparse
import sys

import database
from admin import tokens
from database import export
from linkeddata.imports import import_all
from linkeddata.model import RELEASE, download_vocabularies, pinned_problems, schema_problems, tables_problems, write_schema, write_tables


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m linkeddata", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["model", "check", "import", "export", "push", "backup", "token"])
    parser.add_argument("arguments", nargs="*", help="token: the ORCID iD, the name, and the kinds it may write")
    parser.add_argument("--days", type=int, default=tokens.DEFAULT_DAYS, help="how long a new token is valid")
    args = parser.parse_args()
    if args.command == "model":
        problems = download_vocabularies()
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            sys.exit(1)
        print(f"Wrote {write_schema()}")
        print(f"Wrote {write_tables()}")
    elif args.command == "check":
        problems = pinned_problems()
        if not problems:
            problems = schema_problems() + tables_problems()
        if not problems and (database.STATE_DIR / "platform.sqlite").exists():
            problems = database.differences(database.STATE_DIR / "platform.sqlite")
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            sys.exit(1)
        print(f"The vocabularies, the generated files and the database are those of release {RELEASE}.")
    elif args.command == "import":
        problems = import_all()
        for problem in problems:
            print(f"Not imported: {problem}", file=sys.stderr)
        if problems:
            sys.exit(1)
    elif args.command == "export":
        print("Exported" if export.export() else "Nothing changed")
    elif args.command == "push":
        export.push()
    elif args.command == "backup":
        print(f"Wrote {database.backup()}")
    else:
        if len(args.arguments) < 3:
            parser.error("token needs an ORCID iD, a name, and at least one kind")
        orcid, name, *kinds = args.arguments
        print(tokens.create(orcid, name, kinds, args.days))


if __name__ == "__main__":
    main()
