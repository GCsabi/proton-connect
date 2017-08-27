#!/usr/bin/env python3
import argparse
import os
import random
import re
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
import requests


HOME_DIR = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME_DIR, ".proton-connect")

TMUX_SESSION_NAME = "protonvpn"

config_url = "https://protonvpn.com/download/ProtonVPN_config.zip"
vpn_configs_dir = os.path.join(CONFIG_DIR, "configs")
user_config = os.path.join(CONFIG_DIR, "protonvpn.user")

DOWNLOAD_MESSAGE = """Download openVPN configurations:
Please visit the downloads section in your ProtonVPN account and download the openVPN configuration files,
if you haven't already.
After you have downloaded them, place the configuration files in {}
You can find the configuration files here: https://account.protonvpn.com/downloads""".format(vpn_configs_dir)

_VERBOSE = False


def _write_user_config(credentials=None, pass_path=None):
    """Helper function for writing the user configuration file.

    Writes either the user credentials (username, password),
    or the path to retrieve these credentials from `pass`.

    Args:
        credentials: A tuple containing the username and password (in that order).
            When a tuple with empty strings is passed, nothing is saved and the userfile deleted.
            (default: {None})
        pass_path: The exact path used to get the credentials from `pass` (default: {None})

    Raises:
        ValueError: When neither credentials nor pass_path is given.
    """
    if (credentials is not None and pass_path is not None) or (credentials is None and pass_path is None):
        raise ValueError("Exactly one of credentials or pass_path must be given!")

    lines = []
    if credentials:
        lines = [c for c in credentials if c]

    elif pass_path:
        lines = [pass_path]

    if os.path.exists(user_config):
        print(f"A user configuration already exists ({user_config}).")
        overwrite = input("Overwrite? [yes/no] ").lower()
        if overwrite != "yes":
            return

    sh.chmod("-R", 700, CONFIG_DIR)
    if lines:
        with open(user_config, "w") as f:
            f.writelines("\n".join(lines))
        sh.chmod(600, user_config)

        print(f"Saved to {user_config}")
    else:
        try:
            os.remove(user_config)
        except FileNotFoundError:
            pass

def _print_user_data():
    """Helper function for printing the user credentials.

    Depending on where they are saved (see _write_user_config),
    this either prints the credentials directly from the plaintext file,
    or uses `pass` to acquire them from your password store.
    """
    lines = None
    try:
        with open(user_config, "r") as f:
            lines = [l.strip() for l in f.readlines()]
    except FileNotFoundError:
        print("No prepared credentials found. Please enter them manually or run `proton-connect.py init` to set them up.")
        return

    if len(lines) == 1:
        print(f"Using `{lines[0]}` ...")
        subprocess.run(["pass"] + lines[0].split(" "))

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
        "".join(c for c in conf.split(".")[0] if not c.isnumeric())  # remove numbers
        for conf in configs
        if not "tor" in conf  # tor not relevant for finding countries
    )
    countries = set(c[:-1] if c.endswith("-") else c for c in countries)  # remove trailing dashs from country level VPNs
    if only_countries:
        countries = set(c for c in countries if c in only_countries)

    country_vpn_dict = {
        country: set(
            f"{country}" + re.search(r'(-\d\d)?(-tor)?\.protonvpn\.com', conf).group(0)
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
                if any(c.startswith(vpn) for vpn in country_vpn_dict.get(cntry, []))
            )
        configs = cnfgs

    return country_vpn_dict


def init():
    os.makedirs(CONFIG_DIR, exist_ok=True)

    print(DOWNLOAD_MESSAGE)

    print("\nWhere do you want to save your login data? Press Ctrl+C to quit.")
    choices = {
        0: "Ask every time",
        1: f"plaintext file ({user_config})",
        2: "`pass`"
    }
    for choice, description in choices.items():
        print(f"[{choice}]: {description}")
    try:
        choice = int(input("Enter one of the numbers above (Ctrl+C to cancel): ").strip())
    except KeyboardInterrupt:
        print("\nAborted.")
        return None

    if choice not in choices:
        print("Invalid choice.")
        quit()

    if choice == 0:
        _write_user_config(credentials = ("",))

    elif choice == 1:
        login = input("ProtonVPN login: ")
        password = getpass("ProtonVPN password (leave blank to not save): ")

        _write_user_config(credentials = (login, password))

    elif choice == 2:
        pass_path = input("Please enter the exact path within your password store to get your ProtonVPN credentials from `pass`: ")

        _write_user_config(pass_path = pass_path)

    print("proton-connect is now ready to use.")


def available(only_countries=None):
    try:
        country_configs = _get_available_vpns(only_countries = only_countries)
    except FileNotFoundError:
        print(f"Can't find VPN configurations. Make sure {CONFIG_DIR} is set up or run `proton-connect.py init`")
        return None

    vpn_count = sum([len(confs) for confs in country_configs.values()])

    output_str = f"There are {vpn_count} VPNs available in {len(country_configs)} countries:\n"
    for country, vpns in country_configs.items():
        output_str += f"\n{country} ({len(vpns)})"
        if _VERBOSE:
            output_str += f":\n"
            for vpn in sorted(vpns):
                output_str += f"  {vpn}\n"

    pager(output_str)


def connect(countries=None, vpn_name=None, netcmd=None):
    """Connect to ProtonVPN

    Checks if user is inside tmux;
    if they are, prepares ProtonVPN connection and connects.
    if they are not, connects to or starts tmux session.

    Args:
        countries: A list of country abbreviations (default: {None})
        vpn_name: The name of a specific VPN (default: {None})
        netcmd: The command used to start your network interfaces (default: {None})

    Raises:
        FileNotFoundError: VPN configuration file for a specified VPN doesn't exist.
        ValueError: netcmd failed.
    """
    tmux = os.environ.get("TMUX", None)
    term = os.environ.get("TERM", None)
    if tmux is not None and term == "screen":
        country = None
        vpn = None
        if vpn_name is None and not countries:
            print("Choosing a random VPN from a random county ...", end=" ")
            try:
                country_vpn_dict = _get_available_vpns()
            except FileNotFoundError:
                raise FileNotFoundError(f"Can't find VPN configurations. Make sure {CONFIG_DIR} is set up or run `proton-connect.py init`")
            country = random.choice(list(country_vpn_dict))

        elif vpn_name is None and countries:
            print("Choosing a random VPN from given countries ...", end=" ")
            try:
                country_vpn_dict = _get_available_vpns(only_countries = countries)
            except FileNotFoundError:
                raise FileNotFoundError(f"Can't find VPN configurations. Make sure {CONFIG_DIR} is set up or run `proton-connect.py init`")
            country = random.choice(list(country_vpn_dict))

        if country is not None:
            vpn = random.choice(list(country_vpn_dict[country]))
            print(f"{vpn}")

        if vpn_name is not None:
            # a specific vpn name overrides everything else.
            vpn = vpn_name

        vpn_file = os.path.join(vpn_configs_dir, f"{vpn}.udp1194.ovpn")
        _print_user_data()

        if netcmd is not None:
            print(f"Starting network interfaces: `{netcmd}`")
            if subprocess.run(netcmd.split(" ")).returncode != 0:
                raise ValueError(f"`{netcmd}` failed. Maybe no appropriate permissions?")

        print(f"Connecting to ProtonVPN ({vpn}) now ...")
        try:
            subprocess.run(["sudo", "openvpn", vpn_file])
        except KeyboardInterrupt:
            pass
        except PermissionError:
            pass
        finally:
            print("done.")
            return

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
        try:
            ip_json = requests.get("https://ifconfig.co/json").json()
        except requests.exceptions.ConnectionError:
            print("You are offline.")
        else:
            ip_address = ip_json.get("ip")
            city = ip_json.get("city")
            country = ip_json.get("country")
            print(f"done. Your ip address: {ip_address} ({city}, {country})")

        return


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
        help = f"Initialize proton-connect. This will show you where to download the openVPN configuration files and helps you set up your credentials."
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
    connect_parser.add_argument(
        "--netcmd",
        action = "store",
        help = "The command you use to enable your network interfaces."
    )

    args = parser.parse_args()

    _VERBOSE = args.verbose

    if args.command == "init":
        init()

    elif args.command == "list":
        available(only_countries = args.countries)

    elif args.command == "connect":
        try:
            connect(countries = args.countries, vpn_name = args.vpn, netcmd = args.netcmd)
        except (FileNotFoundError, ValueError) as e:
            print(e)
