import json
import logging
import sys
from json import JSONDecodeError

from adaops import NET_ARG, cardano_cli
from adaops.var import check_file_exists, check_socket_env_var, cmd_str_cleanup

logger = logging.getLogger(__name__)


def get_pool_id(cold_vkey="cold.vkey", output_format="hex", cwd=None):
    """Return pool ID in selected format

    Args:
        cold_vkey: (str) fullpath or filename of cold verification key file.
            If filename is not fullpath, then "cwd" arg should be provided and filename will be looked up in cwd.
        output_format: (str) Accepted output formats are "hex" and "bech32" (default is "hex")

    Returns:
        string value in specified format
    """

    if output_format not in ["hex", "bech32"]:
        logger.error("Wrong output_format '%s' selected. Allowed values are: 'hex', 'bech32'")
        sys.exit(1)

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
        output_format,
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
