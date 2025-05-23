import logging

from adaops import NET_ARG, cardano_cli
from adaops.exceptions import BadCmd
from adaops.var import cmd_str_cleanup

logger = logging.getLogger(__name__)


def generate_node_cert(
    kes_vkey,
    cold_skey,
    cold_counter,
    kes_period,
    output_name="node.cert",
    cwd=None,
):
    """Generate Node Operational certificate.
    Requires renewal as soon as KES key pair is renewed

    Args:
        kes_vkey - (str) path to kes.vkey
        cold_skey - (str) path to cold.skey
        cold_counter - (str) path to cold.counter
        kes_period - (int) current KES period

    Returns:
        str - path to node.cert

    Raises:
        BadCmd: Was not able to generate node cert
    """

    args = [
        "node",
        "issue-op-cert",
        "--kes-verification-key-file",
        kes_vkey,
        "--cold-signing-key-file",
        cold_skey,
        "--operational-certificate-issue-counter",
        cold_counter,
        "--kes-period",
        kes_period,
        "--out-file",
        output_name,
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Was not able to generate node cert")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to generate node cert", cmd=result["cmd"])

    return f"{cwd}/{output_name}"


def generate_stake_reg_cert(output_name="stake.cert", stake_vkey="stake.vkey", cwd=None):
    """Generate stake address registration certificate

    Runs on an air-gapped offline machine

    Args:
        output_name - name of the output file
        stake_vkey - path to stake.vkey
        cwd - working directory

    Returns:
        path to stake registration cert file (str)

    Raises:
        BadCmd: Was not able to create stake registration cert
    """

    args = [
        "stake-address",
        "registration-certificate",
        "--stake-verification-key-file",
        stake_vkey,
        "--out-file",
        output_name,
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Was not able to create stake registration cert")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to create stake registration cert", cmd=result["cmd"])

    return f"{cwd}/{output_name}"


def generate_delegation_cert(output_name, owner_stake_vkey, cold_vkey, cwd=None):
    """Generations stake delegation certificate for the owner

    Runs on an air-gapped offline machine

    Returns:
        path to stake delegation cert file (str)

    Raises:
        BadCmd: Stake Delegation cert creation didn't work
    """

    delegation_certificate_arg = "stake-delegation-certificate"

    args = [
        "stake-address",
        delegation_certificate_arg,
        "--stake-verification-key-file",
        owner_stake_vkey,
        "--cold-verification-key-file",
        cold_vkey,
        "--out-file",
        output_name,
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Delegation cert creation didn't work")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Delegation cert creation didn't work", cmd=result["cmd"])

    return f"{cwd}/{output_name}"


def generate_pool_reg_cert(
    cold_vkey,
    vrf_vkey,
    pledge_amt,
    pool_cost,
    margin,
    reward_stake_vkey,
    owners_stake_vkeys_list,
    metadata_hash,
    metadata_url,
    relay_port,
    relays_ipv4_list=None,
    relays_dns_list=None,
    output_fname="pool-registration.cert",
    cwd=None,
):
    """There might be multiple pool-owner-stake-verification keys
    owners_vkeys - list of string paths to Stake VKEYs.
                   Generate into appropriate argument internaly.

    All relays should be running on the same port.

    Args:
        relays_ipv4_list - list of string in format 'pool_ipv4:port'

    Runs on an air-gapped offline machine

    Returns:
        path to pool registration cert file (str)

    Raises:
        ValueError: metadata_url is longer than 64 characters
        ValueError: owners_stake_vkeys_list should be a list of strings
        RuntimeError: Neither relays_dns_list or relays_ipv4_list supplied
        BadCmd: Pool registration certificate creation didn't work
    """

    if relays_ipv4_list is None:
        relays_ipv4_list = []

    if relays_dns_list is None:
        relays_dns_list = []

    if len(metadata_url) > 64:
        logger.error("Metadata URL is longer than 64 characters: %s", metadata_url)
        raise ValueError("Metadata URL is longer than 64 characters")

    if not isinstance(owners_stake_vkeys_list, list):
        logger.error(
            "owners_stake_vkeys - list of strings with full path to owner stake verification keys"
        )
        raise ValueError(
            "owners_stake_vkeys - list of strings with full path to owner stake verification keys"
        )

    owners_stake_vkeys_args = " ".join(
        [
            f"--pool-owner-stake-verification-key-file {vkey_path}"
            for vkey_path in owners_stake_vkeys_list
        ]
    )

    if not relays_dns_list and not relays_ipv4_list:
        logger.error("Neither relays_dns_list or relays_ipv4_list supplied")
        raise RuntimeError("Neither relays_dns_list or relays_ipv4_list supplied")

    pool_ipv4_relays = [
        f"--pool-relay-ipv4 {relay} --pool-relay-port {relay_port}" for relay in relays_ipv4_list
    ]
    pool_dns_relays = [
        f"--single-host-pool-relay {relay} --pool-relay-port {relay_port}"
        for relay in relays_dns_list
    ]

    final_relays_list = " ".join(pool_ipv4_relays + pool_dns_relays)

    # if debug:
    #     print('relays:', final_relays_list)

    args = [
        "stake-pool",
        "registration-certificate",
        "--cold-verification-key-file",
        cold_vkey,
        "--vrf-verification-key-file",
        vrf_vkey,
        "--pool-pledge",
        pledge_amt,
        "--pool-cost",
        pool_cost,
        "--pool-margin",
        margin,
        "--pool-reward-account-verification-key-file",
        reward_stake_vkey,
        "--metadata-url",
        metadata_url,
        "--metadata-hash",
        metadata_hash,
        *owners_stake_vkeys_args.split(" "),
        *final_relays_list.split(" "),
        *NET_ARG,
        "--out-file",
        output_fname,
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Pool registration certificate creation didn't work")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Pool registration certificate creation didn't work", cmd=result["cmd"])

    return f"{cwd}/{output_fname}"


def generate_deregistration_cert(
    cold_vkey,
    epoch,
    output_name="pool-deregistration.cert",
    cwd=None,
):
    """Generates a pool deregistration certificate required for the pool retirement

    Runs on an air-gapped offline machine

    Returns:
        path to pool deregistration cert file (str)

    Raises:
        BadCmd: Was not able to create pool deregistration cert
    """

    args = [
        "stake-pool",
        "deregistration-certificate",
        "--cold-verification-key-file",
        cold_vkey,
        "--epoch",
        epoch,
        "--out-file",
        output_name,
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Was not able to create pool deregistration cert")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to create pool deregistration cert", cmd=result["cmd"])

    return f"{cwd}/{output_name}"


def generate_stake_dereg_cert(
    stake_vkey,
    output_name="stake-deregistration.cert",
    cwd=None,
):
    """Generates a stake delegation deregistration certificate

    Runs on an air-gapped offline machine

    Returns:
        path to stake delegation deregistration cert file (str)

    Raises:
        BadCmd: Was not able to create stake address deregistration cert
    """

    args = [
        "stake-address",
        "deregistration-certificate",
        "--stake-verification-key-file",
        stake_vkey,
        "--out-file",
        output_name,
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Was not able to create stake address deregistration cert")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to create stake address deregistration cert", cmd=result["cmd"])

    return f"{cwd}/{output_name}"
