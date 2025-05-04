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
