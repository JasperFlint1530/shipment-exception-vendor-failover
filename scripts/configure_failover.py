"""Set the account routing preference used by the shipment service."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.infrai_gateway import RoutingControl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Vendor name to exclude; pass the flag again for another vendor.",
    )
    args = parser.parse_args()
    configured = RoutingControl().set_chat_exclusions(args.exclude)
    print("Routing preference saved:", configured)


if __name__ == "__main__":
    main()
