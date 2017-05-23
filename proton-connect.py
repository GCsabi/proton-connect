#!/usr/bin/env python3
import argparse
import os
import stat
import requests
from getpass import getpass
from zipfile import ZipFile

import sh


HOME_DIR = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME_DIR, ".proton-connect")

config_url = "https://protonvpn.com/download/ProtonVPN_config.zip"
vpn_config_dir = os.path.join(CONFIG_DIR, "ProtonVPN_config")
user_config = os.path.join(CONFIG_DIR, "protonvpn.user")


def init():
    os.makedirs(CONFIG_DIR, exist_ok=True)

    print("Downloading ProtonVPN config files ... ", end = "")
    r = requests.get(config_url, stream=True)
    r.raise_for_status()
    zipfile_path = os.path.join(CONFIG_DIR, "ProtonVPN_config.zip")
    with open(zipfile_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=256):
            f.write(chunk)
    ZipFile(zipfile_path).extractall(CONFIG_DIR)
    os.remove(zipfile_path)
    print("done.")

    print("Do you want to save your login data for the ProtonVPN? ", end = "")
    want_to_save_login = input("[yes/no] ").lower()
    if want_to_save_login != "yes":
        return

    login = input("ProtonVPN login: ")
    password = getpass("ProtonVPN password (leave blank to not save): ")

    if os.path.exists(user_config):
        print(f"A user configuration already exists ({user_config}).")
        overwrite = input("Overwrite? [yes/no] ").lower()
        if overwrite != "yes":
            return

    with open(user_config, "w") as f:
        f.write(f"{login}\n")
        f.write(f"{password}\n")
    sh.chmod("-R", 700, CONFIG_DIR)
    sh.chmod(600, user_config)
    print(f"Saved to {user_config}")

    print("proton-connect is now ready to use.")


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
