import logging
import subprocess
import sys
import json
from tempfile import NamedTemporaryFile

from adaops.var import cmd_str_cleanup, check_file_exists

logger = logging.getLogger(__name__)


def generate_node_cold_keys(name_prefix="cold", cwd=None):
    """Generates Cold/Node key pair

    Runs on air-gapped offline node
    returns tuple of two keys and counter
    """

    cmd = [
        "sh",
        "-c",
        f"""cardano-cli node key-gen \
            --cold-verification-key-file {name_prefix}.vkey \
            --cold-signing-key-file {name_prefix}.skey \
            --operational-certificate-issue-counter-file {name_prefix}.counter""",
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )

    process.wait()
    process_rc = process.returncode
    process_stdout_bytes = process.stdout.read()
    decoded_output = process_stdout_bytes.decode("utf-8")

    if process_rc != 0:
        logger.error("Was not able to generate node's Cold key pair")
        logger.error(decoded_output)
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    return (
        f"{cwd}/{name_prefix}.vkey",
        f"{cwd}/{name_prefix}.skey",
        f"{cwd}/{name_prefix}.counter",
    )


def generate_counter_file(counter_value, node_vkey, name_prefix="cold", cwd=None):
    """Generates new counter file

    Runs on air-gapped offline node
    returns path to a new counter file
    """

    if isinstance(counter_value, int):
        if counter_value <= 0:
            logger.error("counter_value should be a positive integer. Got: '%s'", counter_value)
            sys.exit(1)
    else:
        logger.error("counter_value should be a positive integer. Got: '%s'", counter_value)
        sys.exit(1)

    check_file_exists(node_vkey)

    cmd = [
        "sh",
        "-c",
        f"""cardano-cli node new-counter \
            --cold-verification-key-file {node_vkey} \
            --counter-value {counter_value} \
            --operational-certificate-issue-counter-file {name_prefix}.counter""",
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )

    process.wait()
    process_rc = process.returncode
    process_stdout_bytes = process.stdout.read()
    decoded_output = process_stdout_bytes.decode("utf-8")

    if process_rc != 0:
        logger.error("Was not able to generate new counter file")
        logger.error(decoded_output)
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    return f"{cwd}/{name_prefix}.counter"


def generate_node_vrf_keys(name_prefix="vrf", cwd=None):
    """Generates VRF key pair

    Runs on air-gapped offline node
    returns tuple of two keys
    """

    cmd = [
        "sh",
        "-c",
        f"""cardano-cli node key-gen-VRF \
            --verification-key-file {name_prefix}.vkey \
            --signing-key-file {name_prefix}.skey""",
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )

    process.wait()
    process_rc = process.returncode
    process_stdout_bytes = process.stdout.read()
    decoded_output = process_stdout_bytes.decode("utf-8")

    if process_rc != 0:
        logger.error("Was not able to generate node's VRF key pair")
        logger.error(decoded_output)
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    return (f"{cwd}/{name_prefix}.vkey", f"{cwd}/{name_prefix}.skey")


def generate_node_kes_keys(name_prefix="kes", cwd=None):
    """Generates KES key pair

    Don't forget to reginerate it every 90 days (calculate actual expiration based on genesis file)

    Runs on air-gapped offline node
    returns tuple of two keys
    """

    cmd = [
        "sh",
        "-c",
        f"""cardano-cli node key-gen-KES \
            --verification-key-file {name_prefix}.vkey \
            --signing-key-file {name_prefix}.skey""",
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )

    process.wait()
    process_rc = process.returncode
    process_stdout_bytes = process.stdout.read()
    decoded_output = process_stdout_bytes.decode("utf-8")

    if process_rc != 0:
        logger.error("Was not able to generate node's KES key pair")
        logger.error(decoded_output)
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    return (f"{cwd}/{name_prefix}.vkey", f"{cwd}/{name_prefix}.skey")


def kes_period_info(node_op_cert, network="--mainnet", cwd=None):
    """Retrieve KES information from a node Op cert.
    Returns python dict

    Works only for cardano-cli >=1.35.3
    cardano-cli <=1.34.1 returns wrong data
    https://github.com/input-output-hk/cardano-node/issues/3689
    """

    process_rc = -1
    kesdata = None
    decoded_output = None
    cmd = []

    with NamedTemporaryFile() as tmpf:

        tmp_file_dst = tmpf.name
        print(tmp_file_dst)

        cmd = [
            "sh",
            "-c",
            f"""cardano-cli query kes-period-info {network} \
                --op-cert-file {node_op_cert} \
                --out-file {tmp_file_dst}""",
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
        )

        process.wait()
        process_rc = process.returncode

        process_stdout_bytes = process.stdout.read()
        decoded_output = process_stdout_bytes.decode("utf-8")

        if process_rc == 0:
            with open(tmp_file_dst, "r") as tmpfr:
                kesdata = json.load(tmpfr)

    if process_rc != 0:
        logger.error(f"Was not able to get KES info for the node OP cert: {node_op_cert}")
        logger.error(decoded_output)
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    return kesdata
