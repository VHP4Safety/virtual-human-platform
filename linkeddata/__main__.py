"""The linked data of the platform: python -m linkeddata model."""

import argparse

from linkeddata.model import write_schema


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m linkeddata", description=__doc__)
    parser.add_argument("command", choices=["model"], help="model: generate the approved schema of the model")
    args = parser.parse_args()
    if args.command == "model":
        print(f"Wrote {write_schema()}")


if __name__ == "__main__":
    main()
