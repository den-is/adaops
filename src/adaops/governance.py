import json
import logging
from json import JSONDecodeError

from adaops import cardano_cli
from adaops.exceptions import BadCmd
from adaops.var import cmd_str_cleanup

logger = logging.getLogger(__name__)


def governance_action_vote_with_pool(
    governance_action_tx_id,
    governance_action_index,
    decision,
    cold_verification_key_file,
    output_name,
    cwd=None,
):
    """Create governance vote

    Runs on air-gapped machine

    Args:
        governance_action_tx_id - (str): Governance action transaction ID
        governance_action_index - (str): Governance action index
        decision - (str): Vote decision. One of `yes`, `no`, `abstain`
        cold_verification_key_file - (str): Path to cold verification key file
        output_name - (str): Output file name (not full path)

    Returns:
        Path to governance vote cert file

    Raises:
        BadCmd: Governance action cert creation didn't work
        ValueError: "Invalid decision provided. Must be one of `yes`, `no`, `abstain`"
    """

    decision_map = {
        "yes": "--yes",
        "no": "--no",
        "abstain": "--abstain",
    }

    decision_arg = ""
    if decision not in decision_map.keys():
        msg = "Invalid decision provided. Must be one of `yes`, `no`, `abstain`"
        logger.error(msg)
        raise ValueError(msg)
    else:
        decision_arg = decision_map[decision]

    args = [
        "governance",
        "vote",
        "create",
        decision_arg,
        "--governance-action-tx-id",
        governance_action_tx_id,
        "--governance-action-index",
        governance_action_index,
        "--cold-verification-key-file",
        cold_verification_key_file,
        "--out-file",
        output_name,
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Governance action cert creation didn't work")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Governance action cert creation didn't work", cmd=result["cmd"])

    return f"{cwd}/{output_name}"


def governance_action_view_vote_f(
    vote_file,
    cwd=None,
):
    """View vote data encoded in generated vote file

    Runs anywhere

    Args:
        vote_file - (str): Path to vote file

    Returns:
        JSON output of the vote

    Raises:
        BadCmd: Governance action cert creation didn't work
    """

    args = [
        "governance",
        "vote",
        "view",
        "--output-json",
        "--vote-file",
        vote_file,
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Getting data from the vote file did not work")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Getting data from the vote file did not work", cmd=result["cmd"])

    output = {}
    try:
        output = json.loads(result["stdout"])
    except (JSONDecodeError, ValueError) as err:
        logger.error("Was not able to parse vote file JSON", exc_info=True)
        raise ValueError("Was not able to parse vote file JSON") from err

    return output
