#!/usr/bin/env python3
import argparse
import os
import stat
import requests
import re
from collections import OrderedDict
from getpass import getpass
from pydoc import pager
from zipfile import ZipFile

import sh


HOME_DIR = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME_DIR, ".proton-connect")

config_url = "https://protonvpn.com/download/ProtonVPN_config.zip"
vpn_config_dir = os.path.join(CONFIG_DIR, "ProtonVPN_configs")
user_config = os.path.join(CONFIG_DIR, "protonvpn.user")


_VERBOSE = False


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


def available(only_country=None):
    configs = os.listdir(vpn_config_dir)
    countries = set(
        conf.split(".")[0][:-3]
        for conf in configs
        if not "tor" in conf  # tor not relevant for finding countries
    )
    country_vpn_dict = {
        country: set(
            f"{country}-" + re.search(r'\d\d(-tor)?\.protonvpn\.com', conf).group(0)
            for conf in configs
            if conf.startswith(country)
        )
        for country in countries
    }
    country_vpn_dict = OrderedDict(sorted(country_vpn_dict.items()))

    output_str = f"There are {len(configs)} VPNs available in {len(countries)} countries:\n"
    for country, vpns in country_vpn_dict.items():
        output_str += f"\n{country} ({len(vpns)})"
        if _VERBOSE:
            output_str += f":\n"
            for vpn in sorted(vpns):
                output_str += f"  {vpn}\n"

    pager(output_str)


def connect(country=None, vpn_name=None):
    pass



if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description = f"proton-connect. A wrapper-script for the ProtonVPN.")

    parser.add_argument(
        "-v", "--verbose",
        action = "store_true",
        help = "More output."
    )

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
    connect_parser.add_argument(
        "vpn_name",
        metavar = "VPN",
        action = "store",
        nargs = "?",
        help = "The name of the VPN to which to connect. Chosen randomly, if omitted."
    )

    args = parser.parse_args()

    _VERBOSE = args.verbose

    if args.command == "init":
        init()

    elif args.command == "list":
        available(only_country = args.country)

    elif args.command == "connect":
        connect(country = args.country, vpn_name = args.vpn_name)
