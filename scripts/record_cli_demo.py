from __future__ import annotations

import subprocess
import sys


COMMANDS = [
    ["memory-core", "--help"],
    ["memory-core", "init"],
    ["memory-core", "benchmark"],
]


def main() -> int:
    for command in COMMANDS:
        print("$ " + " ".join(command))
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
