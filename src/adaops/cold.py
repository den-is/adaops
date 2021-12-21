import logging
import subprocess
import sys

from adaops import cmd_str_cleanup

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
