# make sure to not import any other adaops modules here, to avoid circular imports

import logging

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
    or any non zero string, except Falsy values: "", "false", "0", "no", "n", "off".
    In cases where this functions is called not on "string" ENV variables,
    but within code, only `True` (bool) and or any int|float bigger or equal to 1
    """

    if isinstance(val, str):
        return val.lower() in (
            "true",
            "1",
            "yes",
            "y",
            "on",
        ) or val.lower() not in (
            "",
            "false",
            "0",
            "no",
            "n",
            "off",
        )
    elif isinstance(val, (int, float)) and not isinstance(val, bool):
        return val >= 1
    elif isinstance(val, bool):
        return val

    return False


def net_arg(net):
    """Return cardano-cli network argument as a tuple
    Depends on CARDANO_NODE_NETWORK_ID env var.
    We explicitly set network ID for cardano-cli commands which accept this argument.

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
        return ("--testnet-magic", network["network_magic"])

    return ("--mainnet",)


# TODO: To completely deprecate and drop legacy era arguments in all commands
def get_legacy_era_arg(cardano_era, use_legacy_commands=False):
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

    eras_legacy_args_map = {
        "byron": "--byron-era",
        "shelley": "--shelley-era",
        "allegra": "--allegra-era",
        "mary": "--mary-era",
        "alonzo": "--alonzo-era",
        "babbage": "--babbage-era",
    }

    legacy_eras_list = list(eras_legacy_args_map.keys())

    # if cardano_era is not set, default to babbage era
    # empty cardano-node probably means that user is trying to use top level legacy commands
    _cardano_era = "babbage"
    if isinstance(cardano_era, str):
        _cardano_era = cardano_era.lower()

    if not _cardano_era:
        logger.info(
            "CARDANO_ERA ENV variable is not set, going to use 'babbage' era by default",
        )
    elif _cardano_era not in legacy_eras_list and use_legacy_commands:
        logger.error(
            "%s era is not in the list of legacy eras which might require era arg: %s",
            _cardano_era,
            ", ".join(legacy_eras_list),
        )
        raise ValueError(
            f"Selected era {cardano_era.lower()} argument is not in the list of available era arguments: {', '.join(legacy_eras_list)}"  # noqa
        )
    else:
        _cardano_era = cardano_era.lower()

    return eras_legacy_args_map.get(_cardano_era, None)
