import logging
import os
import sys

from dotenv import dotenv_values

from adaops.init_helpers import net_arg
from adaops.wrapper import CardanoCLI

logger = logging.getLogger(__name__)


__version__ = "3.0.0"

config = {
    **os.environ,
    **dotenv_values(".env"),
}


CARDANO_CLI_PATH = config.get("ADAOPS_CARDANO_CLI", "cardano-cli")

CARDANO_ERA = os.getenv("CARDANO_ERA", "conway").lower()

if not CARDANO_ERA:
    logger.error("CARDANO_ERA is not set. Exiting.")
    sys.exit(1)

# NET_ARG returns --mainnet or --testnet <network_magic>
# Depends on the official env var `CARDANO_NODE_NETWORK_ID` and its values
NET_ARG = net_arg(str(config.get("CARDANO_NODE_NETWORK_ID", "mainnet")))

cardano_cli = CardanoCLI(cardano_binary=CARDANO_CLI_PATH, cardano_era=CARDANO_ERA)
