# SPDX-License-Identifier: Apache-2.0
"""Read one explicitly selected local message window through the confined owner."""

import argparse
import json
from pathlib import Path
import sys

import local_messaging as reader


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument(
        "--request", required=True, help="Explicit read-only request JSON"
    )
    parser.add_argument(
        "--state", required=True, help="Owned private window state directory"
    )
    args = parser.parse_args(argv)
    try:
        result = reader.scan(reader.file_json(Path(args.request)), Path(args.state))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (reader.Refused, OSError, ValueError) as exc:
        print(json.dumps({"status": "REFUSED", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
