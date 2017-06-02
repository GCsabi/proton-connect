#!/usr/bin/env python3
import argparse
import os
import random
import re
import requests
import stat
import subprocess
import sys
from collections import OrderedDict
from getpass import getpass
from pydoc import pager
from time import sleep
from zipfile import ZipFile

import libtmux
import sh


HOME_DIR = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME_DIR, ".proton-connect")

TMUX_SESSION_NAME = "protonvpn"

config_url = "https://protonvpn.com/download/ProtonVPN_config.zip"
vpn_configs_dir = os.path.join(CONFIG_DIR, "ProtonVPN_configs")
user_config = os.path.join(CONFIG_DIR, "protonvpn.user")


_VERBOSE = False


def _write_user_config(credentials=None, pass_command=None):
    """Helper function for writing the user configuration file.

    Writes either the user credentials (username, password),
    or the command to retrieve these credentials from `pass`.

    Args:
        credentials: A tuple containing the username and password (in that order). (default: {None})
        pass_command: The exact command used to get the credentials from `pass` (default: {None})

    Raises:
        ValueError: When neither credentials nor pass_command is given.
    """
    if (credentials and pass_command) or ((not credentials) and (not pass_command)):
        raise ValueError("Exactly one of credentials or pass_command must be given!")

    lines = []
    if credentials:
        lines = list(credentials)

    elif pass_command:
        lines = [pass_command]

    if os.path.exists(user_config):
        print(f"A user configuration already exists ({user_config}).")
        overwrite = input("Overwrite? [yes/no] ").lower()
        if overwrite != "yes":
            return

    with open(user_config, "w") as f:
        f.writelines("\n".join(lines))

    sh.chmod("-R", 700, CONFIG_DIR)
    sh.chmod(600, user_config)
    print(f"Saved to {user_config}")

def _print_user_data():
    """Helper function for printing the user credentials.

    Depending on where they are saved (see _write_user_config),
    this either prints the credentials directly from the plaintext file,
    or runs the saved command to acquire them from `pass`.
    """
    lines = None
    with open(user_config, "r") as f:
        lines = [l.strip() for l in f.readlines()]

    if len(lines) == 1:
        print(f"Using `{lines[0]}` ...")
        subprocess.run(lines[0].split(" "))

    elif len(lines) == 2:
        print("\n".join(lines))

    else:
        print("There seems to be something wrong with the configuration.")
        print(f"You should check manually: {user_config}")
        raise LookupError("Error in configuration. Illegal number of lines.")

def _get_available_vpns(only_countries=None):
    """Helper function for listing available VPN configurations.

    Lists and possibly filters ProtonVPN configuration files.

    Args:
        only_countries: A list of countries that shall be listed. Lists all, if omitted. (default: {None})

    Returns:
        A dict containing {country: configs} mappings where country is a str and configs a list.
    """
    configs = os.listdir(vpn_configs_dir)
    countries = set(
        conf.split(".")[0][:-3]
        for conf in configs
        if not "tor" in conf  # tor not relevant for finding countries
    )
    if only_countries:
        countries = set(c for c in countries if c in only_countries)

    country_vpn_dict = {
        country: set(
            f"{country}-" + re.search(r'\d\d(-tor)?\.protonvpn\.com', conf).group(0)
            for conf in configs
            if conf.startswith(country)
        )
        for country in countries
    }
    country_vpn_dict = OrderedDict(sorted(country_vpn_dict.items()))

    if only_countries:
        # filter only configs from filtered countries
        cnfgs = []
        for cntry in only_countries:
            cnfgs.extend(
                c for c
                in configs
                if any(c.startswith(vpn) for vpn in country_vpn_dict[cntry])
            )
        configs = cnfgs

    return country_vpn_dict


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

    print("Where do you want to save your login data?")
    choices = {
        1: f"plaintext file ({user_config})",
        2: "`pass`"
    }
    for choice, description in choices.items():
        print(f"[{choice}]: {description}")
    choice = int(input("Enter one of the numbers above: ").strip())
    if choice not in choices:
        print("Invalid choice.")
        quit()

    if choice == 1:
        login = input("ProtonVPN login: ")
        password = getpass("ProtonVPN password (leave blank to not save): ")

        _write_user_config(credentials = (login, password))

    elif choice == 2:
        pass_command = input("Please enter the exact command you use when getting your ProtonVPN credentials from `pass`: ")

        _write_user_config(pass_command = pass_command)

    print("proton-connect is now ready to use.")


def available(only_countries=None):
    country_configs = _get_available_vpns(only_countries = only_countries)
    vpn_count = sum([len(confs) for confs in country_configs.values()])

    output_str = f"There are {vpn_count} VPNs available in {len(country_configs)} countries:\n"
    for country, vpns in country_configs.items():
        output_str += f"\n{country} ({len(vpns)})"
        if _VERBOSE:
            output_str += f":\n"
            for vpn in sorted(vpns):
                output_str += f"  {vpn}\n"

    pager(output_str)


def connect(countries=None, vpn_name=None):
    tmux = os.environ.get("TMUX", None)
    term = os.environ.get("TERM", None)
    if tmux is not None and term == "screen":
        country = None
        vpn = None
        if vpn_name is None and not countries:
            print("Choosing a random VPN from a random county ...", end=" ")
            country_vpn_dict = _get_available_vpns()
            country = random.choice(list(country_vpn_dict))

        elif vpn_name is None and countries:
            print("Choosing a random VPN from given countries ...", end=" ")
            country_vpn_dict = _get_available_vpns(only_countries = countries)
            country = random.choice(list(country_vpn_dict))

        if country is not None:
            vpn = random.choice(list(country_vpn_dict[country]))
            print(f"{vpn}")

        if vpn_name is not None:
            # a specific vpn name overrides everything else.
            vpn = vpn_name

        vpn_file = os.path.join(vpn_configs_dir, f"{vpn}.udp1194.ovpn")
        _print_user_data()
        print(f"Connecting to ProtonVPN ({vpn}) now ...")
        try:
            subprocess.run(["sudo", "openvpn", vpn_file])
        except KeyboardInterrupt:
            print("done.")

    else:
        print(f"You're not in a tmux session. Trying to attach to {TMUX_SESSION_NAME} ...")
        tmux_server = libtmux.Server()
        try:
            tmux_session = tmux_server.find_where({"session_name": TMUX_SESSION_NAME})
        except libtmux.exc.LibTmuxException:
            tmux_session = None
        if not tmux_session:
            print(f"No tmux session found. Starting new session: {TMUX_SESSION_NAME}")
            tmux_session = tmux_server.new_session(TMUX_SESSION_NAME)

        print(f"Attaching to {TMUX_SESSION_NAME} ...")
        print("Please run this script again inside tmux to connect.")
        sleep(1)  # give a chance to read output

        tmux_session.attach_session()
        print("done.")
        return  # user has to run this again in tmux to actually connect.


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
        help = f"Initialize proton-connect. This will download the openVPN configuration files and let you set up your credentials."
    )

    list_parser = subparsers.add_parser(
        "list",
        help = "List available VPNs, grouped by country."
    )
    list_parser.add_argument(
        "countries",
        metavar = "country",
        action = "store",
        nargs = "*",
        help = "A country from which to list VPNs."
    )

    connect_parser = subparsers.add_parser(
        "connect",
        help = "Connect to ProtonVPN."
    )
    connect_parser.add_argument(
        "vpn",
        metavar = "VPN",
        action = "store",
        nargs = "?",
        help = "The name of the VPN to which to connect. Overrides given countries. Chosen randomly, if omitted."
    )
    connect_parser.add_argument(
        "--countries",
        metavar = "country",
        action = "store",
        nargs = "*",
        help = "A country in which the VPN stands. Chosen randomly, if omitted."
    )

    args = parser.parse_args()

    _VERBOSE = args.verbose

    if args.command == "init":
        init()

    elif args.command == "list":
        available(only_countries = args.countries)

    elif args.command == "connect":
        connect(countries = args.countries, vpn_name = args.vpn)
