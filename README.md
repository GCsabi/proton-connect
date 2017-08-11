# proton-connect.py
A small wrapper script for connecting to the ProtonVPN.

## usage
```
$ proton-connect -h
usage: proton-connect [-h] [-v] {init,list,connect} ...

proton-connect. A wrapper-script for the ProtonVPN.

positional arguments:
  {init,list,connect}
    init               Initialize proton-connect. This will show you where to
                       download the openVPN configuration files and helps you
                       set up your credentials.
    list               List available VPNs, grouped by country.
    connect            Connect to ProtonVPN.

optional arguments:
  -h, --help           show this help message and exit
  -v, --verbose        More output.
```

There are three modes in which this script runs.
Some may take some additional arguments. Use `proton-connect.py MODE -h` for usage instructions for that specific mode.

### init
When running the script in `init` mode, it will ask you to download the OpenVPN configuration files for the ProtonVPNs from [protonvpn.com][config-zips] and extract them to `~/.proton-connect/configs/`.  
It then lets you choose if you want to save your credentials plaintext in a file in that same directory, or access them via [`pass`][pass], or not save them at all.

### list
Running the script in `list` mode, does exactly that. It lists the available VPNs based on the configuration files available in the configs directory.

You can pass the two letter country codes from which you want to list available VPNs.
Additionally, using the verbose mode you can specify if you want to see only the available countries, or also the VPNs.

### connect
Running in `connect` mode first checks, if you are in a `tmux` session.
If you are not in one, it tries to attach to a specific session and if that fails, starts a new one.
This way you don't have to keep the terminal open all the time or possibly Ctrl+C the connection by accident.

When you're in a tmux session, you'll have to run the script again, which then will connect using `openvpn`.
Depending on your arguments, the script will choose a VPN randomly, or use the one you pass it.

Optionally, you may use the `--netcmd` argument to pass a command used for starting your network interfaces.


[config-zips]: https://account.protonvpn.com/downloads
[pass]: https://www.passwordstore.org/
