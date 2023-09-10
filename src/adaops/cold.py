import json
import logging
from tempfile import NamedTemporaryFile

from adaops import NET_ARG, cardano_cli
from adaops.exceptions import BadCmd
from adaops.var import check_file_exists, cmd_str_cleanup

logger = logging.getLogger(__name__)


def generate_node_cold_keys(name_prefix="cold", cwd=None):
    """Generates Cold/Node key pair

    Runs on air-gapped offline node

    Returns:
        Tuple of three paths to cold keys: (cold.vkey, cold.skey, cold.counter)

    Raises:
        BadCmd: Was not able to generate node's Cold key pair
    """

    args = [
        "node",
        "key-gen",
        "--cold-verification-key-file",
        f"{name_prefix}.vkey",
        "--cold-signing-key-file",
        f"{name_prefix}.skey",
        "--operational-certificate-issue-counter-file",
        f"{name_prefix}.counter",
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Was not able to generate node's Cold key pair")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to generate node's Cold key pair", cmd=result["cmd"])

    return (
        f"{cwd}/{name_prefix}.vkey",
        f"{cwd}/{name_prefix}.skey",
        f"{cwd}/{name_prefix}.counter",
    )


def generate_counter_file(counter_value, node_vkey, name_prefix="cold", cwd=None):
    """Generates new counter file

    Returns path to a new counter file

    Runs on air-gapped offline node

    Raises:
        BadCmd: Was not able to generate new counter file
        ValueError: counter_value should be a positive integer
    """

    if isinstance(counter_value, int):
        if counter_value <= 0:
            logger.error("counter_value should be a positive integer. Got: '%s'", counter_value)
            raise ValueError(f"counter_value should be a positive integer. Got: '{counter_value}'")
    else:
        logger.error("counter_value should be a positive integer. Got: '%s'", counter_value)
        raise ValueError(f"counter_value should be a positive integer. Got: '{counter_value}'")

    check_file_exists(node_vkey)

    args = [
        "node",
        "new-counter",
        "--cold-verification-key-file",
        node_vkey,
        "--counter-value",
        counter_value,
        "--operational-certificate-issue-counter-file",
        f"{name_prefix}.counter",
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Was not able to generate new counter file")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to generate new counter file", cmd=result["cmd"])

    return f"{cwd}/{name_prefix}.counter"


def generate_node_vrf_keys(name_prefix="vrf", cwd=None):
    """Generates VRF key pair

    Runs on air-gapped offline node

    Returns:
        Tuple of two paths to VRF keys: (vrf.vkey, vrf.skey)

    Raises:
        BadCmd: Was not able to generate node's VRF key pair
    """

    args = [
        "node",
        "key-gen-VRF",
        "--verification-key-file",
        f"{name_prefix}.vkey",
        "--signing-key-file",
        f"{name_prefix}.skey",
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Was not able to generate node's VRF key pair")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to generate node's VRF key pair", cmd=result["cmd"])

    return (f"{cwd}/{name_prefix}.vkey", f"{cwd}/{name_prefix}.skey")


def generate_node_kes_keys(name_prefix="kes", cwd=None):
    """Generates KES key pair

    Don't forget to reginerate it every 90 days (calculate actual expiration based on genesis file)

    Runs on air-gapped offline node

    Returns:
        Tuple of two paths to KES keys: (kes.vkey, kes.skey)

    Raises:
        BadCmd: Was not able to generate node's KES key pair
    """

    args = [
        "node",
        "key-gen-KES",
        "--verification-key-file",
        f"{name_prefix}.vkey",
        "--signing-key-file",
        f"{name_prefix}.skey",
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Was not able to generate node's KES key pair")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to generate node's KES key pair", cmd=result["cmd"])

    return (f"{cwd}/{name_prefix}.vkey", f"{cwd}/{name_prefix}.skey")


def kes_period_info(node_op_cert):
    """Retrieve KES information from a node Op cert.

    Works only for cardano-cli >=1.35.3
    cardano-cli <=1.34.1 returns wrong data
    https://github.com/input-output-hk/cardano-node/issues/3689

    Returns:
        Dictionary with KES info

    Raises:
        BadCmd: Was not able to get KES info for the node OP cert
    """

    check_file_exists(node_op_cert)

    result = {}
    kesdata = None

    with NamedTemporaryFile() as tmpf:
        tmp_file_dst = tmpf.name
        logger.debug("KES info output dst temp file: %s", tmp_file_dst)

        args = [
            "query",
            "kes-period-info",
            *NET_ARG,
            "--op-cert-file",
            node_op_cert,
            "--out-file",
            tmp_file_dst,
        ]

        result = cardano_cli.run(*args)

        if result["rc"] == 0:
            with open(tmp_file_dst) as tmpfr:
                kesdata = json.load(tmpfr)

    if result["rc"] != 0:
        logger.error(f"Was not able to get KES info for the node OP cert: {node_op_cert}")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd(
            f"Was not able to get KES info for the node OP cert: {node_op_cert}", cmd=result["cmd"]
        )

    return kesdata
