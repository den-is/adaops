import json
import logging
from json import JSONDecodeError

from adaops import cardano_cli
from adaops.exceptions import BadCmd
from adaops.var import cmd_str_cleanup

logger = logging.getLogger(__name__)


def generate_vote_delegation_cert(
    stake_vkey,
    output_name,
    cwd=None,
    always_abstain=False,
    always_no_confidence=False,
    drepid=None,
):
    """Generates certificate for voting power delegation to a DRrep or predefined action "abstain" or "no confidence"

    Since Chang#2 fork you should delegate your voting power to a DRepID to be able to withdraw rewards.
    This is not related to stake delegation certificate this is only for voting power delegation.

    Provide only one of `always_abstain`, `always_no_confidence` or `drepid` hash.
    If by mistake you provide more than one: `always_abstain` > `always_no_confidence` > `drepid_hash`
    I.e. if `always_abstain` is True, then `always_no_confidence` and `drepid_hash` will be ignored
    If `always_abstain` is False and `always_no_confidence` is True, then `drepid_hash` will be ignored

    Conway cardano-node 10.1.3+ only
    Runs on an air-gapped offline machine

    Args:
        stake_vkey - path to stake vkey. Stake key that receives rewards.
        output_name - path to certification file to be created
        cwd - working directory
        always_abstain - boolean, always abstain from voting
        always_no_confidence - boolean, always no confidence in voting
        drepid - hash of the DRepID

    Returns:
        path to vote delegation cert file (str)

    Raises:
        BadCmd: "Vote delegation cert creation didn't work
        ValueError: Provide only one of `always_abstain`, `always_no_confidence` or `drepid_hash`
    """

    if not any([always_abstain, always_no_confidence, drepid]):
        logger.error(
            "Provide only one of `always_abstain`, `always_no_confidence` or `drepid_hash`"
        )
        raise ValueError(
            "Provide only one of `always_abstain`, `always_no_confidence` or `drepid_hash`"
        )

    drep_action_arg = ""

    if drepid:
        # TODO: Add drep key hash validation
        drep_action_arg = f"--drep-key-hash {drepid}"

    if always_no_confidence:
        drep_action_arg = "--always-no-confidence"

    if always_abstain:
        drep_action_arg = "--always-abstain"

    args = [
        "stake-address",
        "vote-delegation-certificate",
        "--stake-verification-key-file",
        stake_vkey,
        *drep_action_arg.split(" "),
        "--out-file",
        output_name,
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Vote delegation cert creation didn't work")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Vote delegation cert creation didn't work", cmd=result["cmd"])

    return f"{cwd}/{output_name}"


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

    Runs on air-gapped machine

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
