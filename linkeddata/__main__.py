"""Commands of the linked data of the platform."""

import argparse
import sys

import database
from admin import tokens
from database import export
from linkeddata.imports import Refused, import_all
from linkeddata.launch import launch
from linkeddata.profile import RELEASE, download_vocabularies, official_problems, tables_problems, terms_problems, write_official, write_tables

COMMANDS = """
    python -m linkeddata model                  write the tables of the model
    python -m linkeddata check                  check the generated files, the vocabularies and the database
                                                against the release of the model
    python -m linkeddata import                 import the weekly sources into the database
    python -m linkeddata launch                 import all sources and make the corrections, once, at launch
    python -m linkeddata export                 write the platform records to the records repository
    python -m linkeddata push                   push the records repository to its remote
    python -m linkeddata backup                 copy the database to PLATFORM_STATE/backups (the latest 14 are kept)
    python -m linkeddata token ORCID NAME KIND  create a write token, such as the first token
"""


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m linkeddata", description=COMMANDS, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["model", "check", "import", "launch", "export", "push", "backup", "token"])
    parser.add_argument("arguments", nargs="*", help="token: ORCID iD, name and kinds")
    parser.add_argument("--days", type=int, default=tokens.DEFAULT_DAYS, help="days a new token is valid")
    args = parser.parse_args()
    if args.command == "model":
        problems = download_vocabularies()
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            sys.exit(1)
        # The tables are made from the shapes, so the shapes are written first.
        print(f"Wrote {write_official()}")
        print(f"Wrote {write_tables()}")
    elif args.command == "check":
        problems = download_vocabularies()
        if not problems:
            problems = terms_problems() + tables_problems() + official_problems()
        if not problems and (database.STATE_DIR / "platform.sqlite").exists():
            problems = database.differences(database.STATE_DIR / "platform.sqlite")
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            sys.exit(1)
        print(f"Vocabularies, generated files and database match release {RELEASE}.")
    elif args.command == "import":
        problems = import_all()
        for problem in problems:
            print(f"Not imported: {problem}", file=sys.stderr)
        if problems:
            sys.exit(1)
    elif args.command == "launch":
        try:
            problems = launch()
        except Refused as refusal:
            sys.exit(f"Not launched: {refusal}")
        for problem in problems:
            print(f"Not imported or corrected: {problem}", file=sys.stderr)
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
            parser.error("token needs an ORCID iD, a name and a kind")
        orcid, name, *kinds = args.arguments
        print(tokens.create(orcid, name, kinds, args.days))


if __name__ == "__main__":
    main()
