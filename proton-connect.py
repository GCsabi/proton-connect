#!/usr/bin/env python3
import argparse
import os


HOME_DIR = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME_DIR, ".proton-connect")



def init():
    pass


def available(country=None):
    pass


def connect(country=None):
    pass



if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description = f"proton-connect. A wrapper-script for the ProtonVPN.")

    # see https://docs.python.org/3/library/argparse.html#sub-commands for docs
    subparsers = parser.add_subparsers(dest = "command")

    init_parser = subparsers.add_parser(
        "init",
        help = f"Initialize proton-connect."
    )

    list_parser = subparsers.add_parser(
        "list",
        help = "List available VPNs, grouped by country."
    )
    list_parser.add_argument(
        "country",
        action = "store",
        nargs = "?",
        help = "The country from which to list VPNs."
    )

    connect_parser = subparsers.add_parser(
        "connect",
        help = "Connect to ProtonVPN."
    )
    connect_parser.add_argument(
        "country",
        action = "store",
        nargs = "?",
        help = "The country in which the VPN stands. Chosen randomly, if omitted."
    )

    args = parser.parse_args()

    if args.command == "init":
        init()

    elif args.command == "list":
        available(country = args.country)

    elif args.command == "connect":
        connect(country = args.country)
