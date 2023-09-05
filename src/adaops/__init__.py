import os

from dotenv import dotenv_values

from adaops.networks import net_arg
from adaops.wrapper import CardanoCLI

__version__ = "0.16.1"

config = {
    **os.environ,
    **dotenv_values(".env"),
}


CARDANO_CLI_PATH = config.get("ADAOPS_CARDANO_CLI", "cardano-cli")

CARDANO_NETWORK = config.get("ADAOPS_NETWORK", "mainnet")
NET_ARG = net_arg(CARDANO_NETWORK)

cardano_cli = CardanoCLI(CARDANO_CLI_PATH)
