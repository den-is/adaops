# make sure to not import any other adaops modules here, to avoid circular imports

import logging
import os

logger = logging.getLogger(__name__)

NETWORK_IDS = {
    "mainnet": {
        "name": "mainnet",
        "type": "mainnet",
        "network_magic": 764824073,
    },
    "1": {
        "name": "preprod",
        "type": "testnet",
        "network_magic": 1,
    },
    "2": {
        "name": "preview",
        "type": "testnet",
        "network_magic": 2,
    },
}


NETWORKS = {
    "mainnet": {
        "type": "mainnet",
        "network_magic": 764824073,
    },
    "preprod": {
        "type": "testnet",
        "network_magic": 1,
    },
    "preview": {
        "type": "testnet",
        "network_magic": 2,
    },
}


def get_truthy_value(val):
    """Return True if val is a truthy value, otherwise False
    Truthy values are: True, "True", "true", "1", 1, "yes", "y", "on"
    """

    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes", "y", "on")

    return val in (True, 1)


def net_arg(net):
    """Return cardano-cli network argument as a tuple

    Tuple will be unpacked into list of arguments.

    Args:
        net (str): cardano network ID, a.k.a network_magic. Example: 'mainnet', '1', '2'
    """

    network = NETWORK_IDS.get(net, None)

    if not network:
        idname_str = ", ".join(
            ["{} for {}".format(i[0], i[1]["name"]) for i in NETWORK_IDS.items()]
        )
        raise ValueError(
            f"'{net}' network ID is not known to Adaops lib. Possible values are: {idname_str}"
        )

    if network["type"] == "testnet":
        return ("--testnet", network["network_magic"])

    return ("--mainnet",)


def get_era_arg(cardano_era=None, use_legacy_commands=False):
    """Return cardano-cli era argument for legacy commands or empty string for non-legacy commands.
    Returns string in format '--<era>-era' or empty string.
    Depends on CARDANO_ERA ENV variable.

    Legacy commands default to specific era.
    E.g. cli 8.20.3.0 (node 8.9.4+) legacy commands default to `--babbage-era`.
    But within adaops library we require to set it explicitly.
    And we always set this argument for all legacy commands which support era argument.

    Starting from "conway" era era argument is not required for most commands.
    conway era has own command group, like `cardano-cli conway ...`
    """

    # if not using legacy commands, return empty string
    # non-legacy commands, grouped under their <era> arg do not require era argument
    if not use_legacy_commands:
        return ""

    eras_lst = ("byron", "shelley", "allegra", "mary", "alonzo", "babbage")

    eras_legacy_args_map = {
        "byron": "--byron-era",
        "shelley": "--shelley-era",
        "allegra": "--allegra-era",
        "mary": "--mary-era",
        "alonzo": "--alonzo-era",
        "babbage": "--babbage-era",
    }

    if not cardano_era:
        logger.info(
            "CARDANO_ERA ENV variable is not set, going to use 'babbage' era as default",
        )
        cardano_era = "babbage"
    elif cardano_era.lower() not in eras_lst and use_legacy_commands:
        logger.error(
            "%s era is not in the list of available eras: %s",
            cardano_era,
            ", ".join(eras_lst),
        )
        raise ValueError(
            f"Selected era {cardano_era.lower()} argument is not in the list of available era arguments: {', '.join(eras_lst)}"
        )
    else:
        cardano_era = cardano_era.lower()

    # TODO: support non legacy commands as well
    ## non legacy commands are grouped under era commnda group, like `cardano-cli conway ...`
    if use_legacy_commands:
        era_arg = eras_legacy_args_map.get(cardano_era.lower(), None)
        if not era_arg:
            raise ValueError(
                f"Selected era '{cardano_era.lower()}' if not available for legacy commands."
                " Check if ERA has own command group, instead of using it as an argument."
            )
        else:
            return era_arg
