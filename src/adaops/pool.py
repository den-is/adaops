import json
import logging
import sys
from json import JSONDecodeError

from adaops import cardano_cli, NET_ARG
from adaops.var import check_file_exists, cmd_str_cleanup, check_socket_env_var

logger = logging.getLogger(__name__)


def get_pool_id(cold_vkey="cold.vkey", cwd=None):
    """Returns Pool's ID"""

    if cwd:
        checked_f = check_file_exists(f"{cwd}/{cold_vkey}")
    else:
        checked_f = check_file_exists(cold_vkey)

    args = [
        "stake-pool",
        "id",
        "--cold-verification-key-file",
        checked_f,
        "--output-format",
        "hex",
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Not able to get pool ID")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        sys.exit(1)

    return result["stdout"].strip()


def get_pool_stake_snapshot(pool_id):
    """Get active pool stake snapshot.

    Requires RAM. In case if cardano-node process is killed because of OOM long validation process might occur.

    CARDANO_NODE_SOCKET_PATH env var required
    """

    check_socket_env_var()

    args = [
        "query",
        "stake-snapshot",
        "--stake-pool-id",
        pool_id,
        *NET_ARG,
    ]

    result = cardano_cli.run(*args)

    if result["rc"] != 0:
        logger.error(
            "Was not able to get blockchain stakes snapshot. "
            "Check that your host has enough memory."
        )
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        sys.exit(1)

    try:
        output = json.loads(result["stdout"])
    except (JSONDecodeError, ValueError):
        logger.error("Was not able to read Stakes Snapshot JSON", exc_info=1)
        sys.exit(1)

    return output


def get_pool_params(pool_id):
    """Get active pool parameters.

    Requires RAM. In case if cardano-node process is killed because of OOM long validation process might occur.

    CARDANO_NODE_SOCKET_PATH env var required
    """

    check_socket_env_var()

    args = [
        "query",
        "pool-params",
        "--stake-pool-id",
        pool_id,
        *NET_ARG,
    ]

    result = cardano_cli.run(*args)

    if result["rc"] != 0:
        logger.error("Was not able to get pool params")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        sys.exit(1)

    try:
        output = json.loads(result["stdout"])
    except (JSONDecodeError, ValueError):
        logger.error("Was not able to decode Pool Params JSON", exc_info=1)
        sys.exit(1)

    return output
