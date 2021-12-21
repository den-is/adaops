import json
import logging
import os
import subprocess
import sys
from json import JSONDecodeError

from adaops.var import check_file_exists, cmd_str_cleanup

logger = logging.getLogger(__name__)


def get_pool_id(cold_vkey="cold.vkey", cwd=None):
    """Returns Pool's ID"""

    if cwd:
        checked_f = check_file_exists(f"{cwd}/{cold_vkey}")
    else:
        checked_f = check_file_exists(cold_vkey)

    cmd = [
        "sh",
        "-c",
        f"cardano-cli stake-pool id --cold-verification-key-file {checked_f} --output-format hex",
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
        logger.error("Not able to get pool ID")
        logger.error(decoded_output)
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))

        sys.exit(1)

    return decoded_output.strip()


def get_pool_stake_snapshot(pool_id, network="--mainnet"):
    """Get active pool stake snapshot.

    CARDANO_NODE_SOCKET_PATH env var required
    """

    cmd = ["sh", "-c", f"cardano-cli query stake-snapshot --stake-pool-id {pool_id} {network}"]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=dict(os.environ, CARDANO_NODE_SOCKET_PATH="/opt/cardano/sockets/node.socket"),
    )

    process.wait()
    process_rc = process.returncode
    process_stdout_bytes = process.stdout.read()

    if process_rc != 0:
        logger.error(
            "Was not able to get blockchain stakes snapshot. "
            "Check that your host has enough memory."
        )
        logger.error(process_stdout_bytes.decode("utf-8"))
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    try:
        output = json.loads(process_stdout_bytes)
    except (JSONDecodeError, ValueError):
        logger.error("Was not able to read Stakes Snapshot JSON", exc_info=1)
        sys.exit(1)

    return output


def get_pool_params(pool_id, network="--mainnet"):
    """Get active pool parameters.

    CARDANO_NODE_SOCKET_PATH env var required
    """

    cmd = ["sh", "-c", f"cardano-cli query pool-params --stake-pool-id {pool_id} {network}"]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=dict(os.environ, CARDANO_NODE_SOCKET_PATH="/opt/cardano/sockets/node.socket"),
    )

    process.wait()
    process_rc = process.returncode
    process_stdout_bytes = process.stdout.read()

    if process_rc != 0:
        logger.error("Was not able to get pool params")
        logger.error(process_stdout_bytes.decode("utf-8"))
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    try:
        output = json.loads(process_stdout_bytes)
    except (JSONDecodeError, ValueError):
        logger.error("Was not able to decode Pool Params JSON", exc_info=1)
        sys.exit(1)

    return output
