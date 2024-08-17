import os

from dotenv import dotenv_values

from adaops.init_helpers import get_legacy_era_arg, get_truthy_value, net_arg
from adaops.wrapper import CardanoCLI

__version__ = "1.0.0"

config = {
    **os.environ,
    **dotenv_values(".env"),
}


CARDANO_CLI_PATH = config.get("ADAOPS_CARDANO_CLI", "cardano-cli")

CARDANO_ERA = os.getenv("CARDANO_ERA", "").lower()

# NET_ARG returns --mainnet or --testnet <network_magic>
# Depends on the official env var `CARDANO_NODE_NETWORK_ID` and its values
NET_ARG = net_arg(str(config.get("CARDANO_NODE_NETWORK_ID", "mainnet")))

# TODO: To drop in the future
CARDANO_CLI_LEGACY_COMMANDS = get_truthy_value(config.get("CARDANO_CLI_LEGACY_COMMANDS", False))

# LEGACY_ERA_ARG returns --shelley-era, --babbage-era, etc
LEGACY_ERA_ARG = get_legacy_era_arg(
    cardano_era=CARDANO_ERA,
    use_legacy_commands=CARDANO_CLI_LEGACY_COMMANDS,
)

cardano_cli = CardanoCLI(
    cardano_binary=CARDANO_CLI_PATH,
    cardano_era=CARDANO_ERA,
    use_legacy_commands=CARDANO_CLI_LEGACY_COMMANDS,
)
