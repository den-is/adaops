NETWORKS = {
    "preview": {
        "type": "testnet",
        "network_magic": 2,
    },
    "preprod": {
        "type": "testnet",
        "network_magic": 1,
    },
    "mainnet": {
        "type": "mainnet",
        "network_magic": 764824073,
    },
}


def net_arg(net):
    """Return cardano-cli network argument as list"""

    network = NETWORKS.get(net, None)

    if not network:
        raise ValueError(
            f"Adaops lib does know about the '{net}' network. Possible values are {','.join(list(NETWORKS.keys()))}"
        )

    result = []

    result.append(f"--{network['type']}")

    if network["type"] == "testnet":
        result.append(network["network_magic"])

    return result
