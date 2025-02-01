import json
import logging
import time
from json import JSONDecodeError
from timeit import default_timer as timer

from adaops import LEGACY_ERA_ARG, NET_ARG, cardano_cli
from adaops.exceptions import BadCmd
from adaops.var import check_file_exists, check_socket_env_var, cmd_str_cleanup, get_balances

logger = logging.getLogger(__name__)


def build_tx(
    tx_in_list,
    tx_out_list,
    fee=0,
    invalid_hereafter=None,
    invalid_before=None,
    withdrawal=None,
    certs=None,
    mint=None,
    minting_script_file=None,
    metadata_file=None,
    output_fname="tx.draft",
    era_arg=None,
    extra_args=None,
    draft=True,
    cwd=None,
):
    """Generates unsigned transaction file. Either draft or raw.
    Usually should be run on air-gapped machine.

    Is able to generate transactions:
    - Between two or more peers - "simple transaction between receiving addresses"
    - Withdrawing staking rewards from a stake address
    - Registering certificates on the blockchain
    - Sending transaction with metadata attached. JSON metadata file should be provided.
    - Mint native tokens

    Args:
        tx_in_list  - list of input transaction hashes with index. list of strings.
                    string format: "tx_hash#tx_idx"
        tx_out_list - list of output/destination addresses. string format: "address+amount"
        fee - transaction fee in Lovelaces. For draft transactions, since "Conway" fee should be something real such as 200_000
        invalid_hereafter - "now_slot + int" - slot number after which the transaction is invalid
        invalid_before - known slot number if feature before transaction should be submitted
        withdrawal  - string. if provided should be in form "stake_addr+withdrawal_amount"
        certs - certificates to include and register on blockchain.
                should be list of strings representing full path to certificates.
        mint - string. minting policy string. Example: "1 policyid.tokenname + 1 policyid.tokenname2"
                where tokenname is hex string
        minting_script_file - string. mint policy sctipt file path
        output_fname - string. output file path.
                        convention used in many examples:
                        "tx.draft" for a transaction draft
                        "tx.raw" for the actual transaction.

    Returns:
        path to transaction file (str)

    Raises:
        ValueError: Selected era argument is not in the list of available era arguments
        ValueError: "certs" argument should be a list.
        RuntimeError: Got "mint" string, but minting-script-file is missing. Both are required.
        RuntimeError: Got "minting_script_file", but not a "mint"string . Both are required.
        BadCmd: Was not able to build Transaction File
    """

    tx_in_args = " ".join([f"--tx-in {utxo}" for utxo in tx_in_list])

    tx_out_args = " ".join([f"--tx-out {tx_out_dst}" for tx_out_dst in tx_out_list])

    if certs is None:
        certs_args = ""
    elif isinstance(certs, list):
        if len(certs) > 0:
            certs_args = " ".join([f"--certificate-file {cert}" for cert in certs])
    else:
        logger.error('"certs" argument should be a list. Received: %s', certs)
        raise ValueError('"certs" argument should be a list.')

    withdrawal_args = ""
    if withdrawal:
        withdrawal_args = f"--withdrawal {withdrawal}"

    invalid_hereafter_arg = ""
    if invalid_hereafter is not None:
        invalid_hereafter_arg = f"--invalid-hereafter {invalid_hereafter}"

    invalid_before_arg = ""
    if invalid_before is not None:
        invalid_before_arg = f"--invalid-before {invalid_before}"

    _extra_args = ""
    if extra_args:
        _extra_args = extra_args

    minting_args = ""
    if mint and minting_script_file:
        check_file_exists(minting_script_file)
        minting_args = f'--mint="{mint}" --minting-script-file {minting_script_file}'
    elif mint and not minting_script_file:
        logger.error('Got "mint" string, but minting-script-file is missing. Both are required.')
        raise RuntimeError(
            'Got "mint" string, but minting-script-file is missing. Both are required.'
        )
    elif minting_script_file and not mint:
        logger.error('Got "minting_script_file", but not a "mint"string . Both are required.')
        raise RuntimeError(
            'Got "minting_script_file", but not a "mint"string . Both are required.'
        )

    metadata_json_file_arg = ""
    if metadata_file:
        logger.info("Got --metadata-json-file. Going to check if it exists.")
        check_file_exists(metadata_file)
        metadata_json_file_arg = f"--metadata-json-file {metadata_file}"

    args = list(
        filter(
            None,
            [
                "transaction",
                "build-raw",
                LEGACY_ERA_ARG,
                *tx_in_args.split(" "),
                *tx_out_args.split(" "),
                *invalid_hereafter_arg.split(" "),
                *invalid_before_arg.split(" "),
                "--fee",
                # if you pass fee=0 (usually during a draft tx build)
                # filter() will remove that value from the list
                # so convert value to string early
                str(fee),
                "--out-file",
                output_fname,
                *certs_args.split(" "),
                *withdrawal_args.split(" "),
                *minting_args.split(" "),
                *metadata_json_file_arg.split(" "),
                *_extra_args.split(" "),
            ],
        )
    )

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        if draft:
            logger.error("Was not able to build Transaction Draft")
        else:
            logger.error("Was not able to build Raw Transaction")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to build Transaction File", cmd=result["cmd"])

    return f"{cwd}/{output_fname}"


def get_tx_fee(
    tx_file="tx.draft",
    tx_in_count=1,
    tx_out_count=1,
    witnesses=1,
    byron_witnesses=0,
    reference_script_size=0,
    protocol_fpath="../protocol.json",
    cwd=None,
):
    """Witnesses are the number of keys that will be signing the transaction.
    Runs on online node.

    Returns:
        int - transaction fee in Lovelaces

    Raises:
        BadCmd: Was not able to calculate a transaction fee

    Examples:
        - at least payment.skey - usual transaction
        - cold.skey stake.skey payment.skey - pool registration
        - cold.skey payment.skey - pool deregisratoin
        - payment.skey stake.skey - stake address registration
    """

    check_socket_env_var()
    _protocol_fpath = check_file_exists(protocol_fpath)

    args = [
        "transaction",
        "calculate-min-fee",
        "--tx-body-file",
        tx_file,
        "--tx-in-count",
        tx_in_count,
        "--tx-out-count",
        tx_out_count,
        "--witness-count",
        witnesses,
        "--byron-witness-count",
        byron_witnesses,
        "--reference-script-size",
        reference_script_size,
        "--protocol-params-file",
        _protocol_fpath,
        "--output-json",
        *NET_ARG,
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Was not able to calculate a transaction fee")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to calculate a transaction fee", cmd=result["cmd"])

    try:
        fee_lovelace = json.loads(result["stdout"])["fee"]
        return fee_lovelace
    except (JSONDecodeError, ValueError) as err:
        logger.error("Was not able to parse JSON output", exc_info=True)
        raise ValueError("Was not able to parse JSON output") from err


def min_utxo(tx_out, protocol_fpath, era_arg="--alonzo-era"):
    """Calculates minimum required UTXO amount in tx_out to send with assets
    Since Alonzo era.

    Args:
        tx_out - actual real tx_out string
            single asset: receiver_addr+receiver_ada+"1 policyid.tokenname"
            multi asset: receiver_addr+receiver_ada+"1 policyid.tokenname1 + 1 policyid.tokenname2"
            receiver_addr and receiver_ada ara not important and can be some draft values
        protocol_fpath - path to protocol parameters JSON file

    Returns:
        int - minimum required UTXO amount in Lovelaces

    Raises:
        ValueError: Selected era argument is not in the list of available era arguments
        BadCmd: Was not able to calculate minimum required UTXO amount for assets transaction
    """

    _protocol_fpath = check_file_exists(protocol_fpath)

    args = [
        "transaction",
        "calculate-min-required-utxo",
        LEGACY_ERA_ARG,
        "--protocol-params-file",
        _protocol_fpath,
        "--tx-out",
        tx_out,
    ]

    result = cardano_cli.run(*list(filter(None, args)))

    if result["rc"] != 0:
        logger.error(
            "Was not able to calculate minimum required UTXO amount for assets transaction"
        )
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd(
            "Was not able to calculate minimum required UTXO amount for assets transaction"
        )

    tx_fee_lovelace = int(result["stdout"].split(" ")[1])

    return tx_fee_lovelace


def sign_tx(tx_file, signing_keys_list, output_fname="tx.signed", cwd=None):
    """Witnesses are the number of keys that will be signing the transaction.

    Runs on air-gapped offline machine. All signing and cert generation happens on offline machine

    Returns:
        path to signed transaction file (str)

    Raises:
        BadCmd: Signing TX did not work.

    Examples:
        - at least "payment.skey" - usual transaction
        - "payment.skey", "stake.skey" - stake address registration
        - "cold.skey", "stake.skey", "payment.skey" - pool registration
        - "cold.skey", "payment.skey" - pool deregisration
    """

    signing_keys_args = " ".join([f"--signing-key-file {skey}" for skey in signing_keys_list])

    args = [
        "transaction",
        "sign",
        "--tx-body-file",
        tx_file,
        *signing_keys_args.split(" "),
        *NET_ARG,
        "--out-file",
        output_fname,
    ]

    result = cardano_cli.run(*list(filter(None, args)), cwd=cwd)

    if result["rc"] != 0:
        logger.error("Signing TX did not work.")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Signing TX did not work.", cmd=result["cmd"])

    return f"{cwd}/{output_fname}"


def submit_tx(signed_tx_f="tx.signed", cwd=None):
    """Submitting signed transaction to blockchain

    Requires CARDANO_NODE_SOCKET env variable
    Should run on online machine

    Returns:
        True if transaction was submitted successfully

    Raises:
        BadCmd: Submiting TX did not work.
    """

    check_socket_env_var()
    _signed_tx_f = check_file_exists(signed_tx_f)

    args = [
        "transaction",
        "submit",
        "--tx-file",
        _signed_tx_f,
        *NET_ARG,
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Submiting TX did not work.")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Submiting TX did not work.", cmd=result["cmd"])

    tx_id = get_tx_id(signed_tx_f)
    logger.info("Successfully submitted transaction %s", tx_id)

    return True


def get_tx_id(tx_file=None, tx_body_file=None):
    """Return transaction ID using either TX body file, or signed/final TX file

    One of two inputs is required.
    tx_body_file - raw transaction draft file, unsigned
    tx_file - signed transaction file. Has priority if both files provided.

    Returns:
        tx_id (string)

    Raises:
        RuntimeError: Either 'tx_file' or 'tx_body_file' should be provided. None provided
        BadCmd: Was not able to get transaction ID
    """

    if not tx_file and not tx_body_file:
        logger.error("Either 'tx_file' or 'tx_body_file' should be provided. None provided")
        raise RuntimeError("Either 'tx_file' or 'tx_body_file' should be provided. None provided")

    if tx_body_file and not tx_file:
        check_file_exists(tx_body_file)
        args = ["transaction", "txid", "--tx-body-file", tx_body_file]
    else:
        check_file_exists(tx_file)
        args = ["transaction", "txid", "--tx-file", tx_file]

    result = cardano_cli.run(*list(filter(None, args)))

    if result["rc"] != 0:
        logger.error("Was not able to get transaction ID")
        logger.error(result["stderr"].strip())
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to get transaction ID", cmd=result["cmd"])

    tx_id = result["stdout"].strip()

    return tx_id


def view_tx_info(tx_file=None, tx_body_file=None):
    """Return info about transaction

    Args:
        tx_file: Input filepath of the JSON Tx (signed). Defaults to None.
        tx_body_file: Input filepath of the JSON TxBody (unsigned). Defaults to None.

    Returns:
        output (string)

    Raises:
        RuntimeError: Either 'tx_file' or 'tx_body_file' should be provided. None provided
        BadCmd: Was not able to get transaction info
    """

    if not tx_file and not tx_body_file:
        logger.error("Either 'tx_file' or 'tx_body_file' should be provided. None provided")
        raise RuntimeError("Either 'tx_file' or 'tx_body_file' should be provided. None provided")

    if tx_body_file and not tx_file:
        check_file_exists(tx_body_file)
        args = ["transaction", "view", "--tx-body-file", tx_body_file, "--output-json"]
    else:
        check_file_exists(tx_file)
        args = ["transaction", "view", "--tx-file", tx_file, "--output-json"]

    # cmd_group="debug" since cardano-cli 9.4.1.0
    result = cardano_cli.run(*args, cmd_group="debug")

    if result["rc"] != 0:
        logger.error("Was not able to get transaction info")
        logger.error(result["stderr"].strip())
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        BadCmd("Was not able to get transaction info", cmd=result["cmd"])

    output = result["stdout"].strip()

    return output


def wait_for_tx(address, tx_id, timeout=60):
    """Return transaction ID using either TX body file, or signed/final TX file

    One of the inputs is required. In case if both are supplied 'tx_file' will take precedence.
    """
    start = timer()
    end = 0

    tx_arrived = False
    timeouted = False

    while not tx_arrived:
        if (end - start) >= timeout:
            timeouted = True
            break

        utxos = get_balances(address=address)

        for utxo in utxos.keys():
            utxo_hash = utxo.split("#")[0]
            if utxo_hash == tx_id:
                end_time = int(round(end - start, 0))
                tx_arrived = True
                logger.info("TX %s appeared in %d sec", tx_id, end_time)
                return

        time.sleep(1)
        end = timer()

    elapsed_time = int(round(end - start, 0))

    if timeouted:
        logger.warning("TX %s timeouted after %d seconds", tx_id, elapsed_time)
