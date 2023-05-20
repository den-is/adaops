import json
import logging
import math
import sys
import time
from timeit import default_timer as timer

from adaops import cardano_cli, NET_ARG
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
    - Withdrawing staking rewards from a stake address.
    - Registering certificates on the blockchain.

    tx_in_list  - list of input transaction hashes with index. list of strings.
                  string format: "tx_hash#tx_idx"
    tx_out_list - list of output/destination addresses. string format: "address+amount"
    withdrawal  - string. if provided should be in form "stake_addr+withdrawal_amount"
    certs - certificates to include and register on blockchain.
            should be list of strings representing full path to certificates.
    output_fname - convention used in many examples:
                    "tx.draft" for a transaction draft
                    "tx.raw" for the actual transaction.
    """

    eras_args = [
        "",
        None,
        "--byron-era",
        "--shelley-era",
        "--allegra-era",
        "--mary-era",
        "--alonzo-era",
        "--babbage-era",
    ]

    if era_arg not in eras_args:
        logger.error(
            "Selected era %s argument is not in the list of available era arguments: %s",
            era_arg,
            eras_args,
        )
        logger.error("Exiting")
        sys.exit(1)
    elif not era_arg:
        era_arg = ""

    tx_in_args = " ".join(["--tx-in {}".format(utxo) for utxo in tx_in_list])

    tx_out_args = " ".join(["--tx-out {}".format(tx_out_dst) for tx_out_dst in tx_out_list])

    if certs is None:
        certs_args = ""
    elif isinstance(certs, list):
        if len(certs) > 0:
            certs_args = " ".join(["--certificate-file {}".format(cert) for cert in certs])
    else:
        logger.error('"certs" argument should be a list. Received: %s', certs)
        logger.error("Exiting")
        sys.exit(1)

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
        logger.error(
            'Got "mint" string, but minting-script-file is missing. Both are required. Exiting.'
        )
        sys.exit(1)
    elif minting_script_file and not mint:
        logger.error(
            'Got "minting_script_file", but not a "mint"string . Both are required. Exiting.'
        )
        sys.exit(1)

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
                era_arg,
                *tx_in_args.split(" "),
                *tx_out_args.split(" "),
                *invalid_hereafter_arg.split(" "),
                *invalid_before_arg.split(" "),
                "--fee",
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
        sys.exit(1)

    return f"{cwd}/{output_fname}"


def get_tx_fee(
    tx_file="tx.draft",
    tx_in_count=1,
    tx_out_count=1,
    witnesses=1,
    byron_witnesses=0,
    protocol_fpath="../protocol.json",
    cwd=None,
):
    """Witnesses are the number of keys that will be signing the transaction.
    Runs on online node.

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
        str(tx_in_count),
        "--tx-out-count",
        tx_out_count,
        "--witness-count",
        str(witnesses),
        "--byron-witness-count",
        str(byron_witnesses),
        "--protocol-params-file",
        _protocol_fpath,
        *NET_ARG,
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Was not able to calculate fees")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        sys.exit(1)

    tx_fee_lovelace = int(result["stdout"].split(" ")[0])

    return tx_fee_lovelace


def min_utxo(tx_out, protocol_fpath, era_arg="--alonzo-era"):
    """Calculates minimum required UTXO amount in tx_out to send with assets
    Since Alonzo era.
    Returns int Lovelaces.

    tx_out - actual real tx_out string
        single asset: receiver_addr+receiver_ada+"1 policyid.tokenname"
        multi asset: receiver_addr+receiver_ada+"1 policyid.tokenname1 + 1 policyid.tokenname2"
        receiver_addr and receiver_ada ara not important and can be some draft values

    protocol_fpath - path to protocol parameters JSON file
    """

    _protocol_fpath = check_file_exists(protocol_fpath)

    eras_args = [
        "",
        None,
        "--byron-era",
        "--shelley-era",
        "--allegra-era",
        "--mary-era",
        "--alonzo-era",
        "--babbage-era",
    ]

    if era_arg not in eras_args:
        logger.error(
            "Selected era %s argument is not in the list of available era arguments: %s",
            era_arg,
            eras_args,
        )
        logger.error("Exiting")
        sys.exit(1)
    elif not era_arg:
        era_arg = ""

    args = [
        "transaction",
        "calculate-min-required-utxo",
        "calculate-min-required-utxo",
        era_arg,
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
        sys.exit(1)

    tx_fee_lovelace = int(result["stdout"].split(" ")[1])

    return tx_fee_lovelace


def min_utxo_math(tx_out, protocol_fpath, hex_name=True, era="alonzo"):
    """Calculate minimum required UTXO for assets transfer using manual/scientific method provided in Cardano papers.
    Method added as a historical record and reference for checking calculations.

    Note that with an upcoming upgrade to Babbage era, the protocol parameter coinsPerUTxOWord
    changes to coinsPerUTxOByte, which means that the price will be calculated per
    one byte instead of per eight bytes. The calculation will therefore look as follows:
    minUTxoVal = (160 + sizeInBytes (TxOut)) * coinsPerUTxOByte.
    For more details, see: https://cips.cardano.org/cips/cip55/

    Sources:
    https://docs.cardano.org/native-tokens/minimum-ada-value-requirement
    https://github.com/input-output-hk/cardano-ledger/blob/8b6f8e1a75034ca66fd66a39d437252eec927d71/doc/explanations/min-utxo-alonzo.rst
    """

    _protocol_fpath = check_file_exists(protocol_fpath)

    protocol_params = {}
    with open(_protocol_fpath, "r") as params_json_f:
        protocol_params = json.load(params_json_f)

    # chain constants, based on the specifications: https://hydra.iohk.io/build/5949624/download/1/shelley-ma.pdf
    k0 = 0  # coinSize=0 in mary-era, 2 in alonzo-era
    if era == "alonzo":
        k0 = 2

    k1 = 6
    k2 = 12  # assetSize=12
    k3 = 28  # pidSize=28
    k4 = 8  # word=8 bytes
    utxoEntrySizeWithoutVal = 27  # 6+txOutLenNoVal(14)+txInLen(7)
    adaOnlyUTxOSize = utxoEntrySizeWithoutVal + k0

    minUTXOValue = protocol_params.get("minUTxOValue")
    utxoCostPerWord = protocol_params.get("utxoCostPerWord")
    if era == "alonzo":
        # at the moment of writing (20211206) returns: 999978
        minUTXOValue = utxoCostPerWord * adaOnlyUTxOSize

    # preload it with the minUTXOValue (1ADA), will be overwritten if costs are higher
    # minOutUTXO - should 1ADA - 1,000,000Lovelace
    result = minUTXOValue

    parts = tx_out.split("+")  # [ addr, bal, asset[s...] ]

    print(parts)

    if len(parts) > 2:
        idx = 2  # skip, addr and bal, start with assets
        pidCollector = []  # holds the list of individual policyIDs
        assetsCollector = []  # holds the list of individual assetHases (policyID+assetName)
        nameCollector = []  # holds the list of individual assetNames(hex format)

        # iterate over assets attached to UTXO
        while len(parts) > idx:
            # separate assetamount from asset_hash(policyID.assetName)
            complete_asset_info = list(filter(None, parts[idx].replace('"', "").split(" ")))
            asset_hash = complete_asset_info[1]

            # split asset_hash_name into policyID and assetName(hex)
            # later when we change the tx-out format to full hex format
            # this can be simplified into a stringsplit
            asset_hash_data_lst = asset_hash.split(".")
            asset_hash_policy = asset_hash_data_lst[0]

            asset_hash_hexname = asset_hash_data_lst[1]

            # if asset name is in ASCII format
            if not hex_name:
                asset_hash_hexname = asset_hash_data_lst[1].encode("utf-8").hex()

            # Testing conversion in bash:
            # echo -n $1 | xxd -b -ps -c 80 | tr -d '\n'
            # input: b3c95a579b99059f521f8a1a78a75b94
            # correct result: 6233633935613537396239393035396635323166386131613738613735623934
            # wrong result: 2d6e2062336339356135373962393930353966353231663861316137386137356239340a

            pidCollector.append(asset_hash_policy)
            assetsCollector.append(f"{asset_hash_policy}{asset_hash_hexname}")
            if asset_hash_hexname:
                nameCollector.append(asset_hash_hexname)

            idx += 1

    # get uniq entries
    numPIDs = len(set(pidCollector))
    numAssets = len(set(assetsCollector))

    # get sumAssetNameLengths
    # divide consolidated hexstringlength by 2 because 2 hex chars -> 1 byte
    sumAssetNameLengths = int(len("".join(set(nameCollector)).strip()) / 2)

    roundupBytesToWords = math.floor(
        (numAssets * k2 + sumAssetNameLengths + numPIDs * k3 + (k4 - 1)) / k4
    )
    tokenBundleSize = k1 + roundupBytesToWords

    minAda = math.floor(minUTXOValue / adaOnlyUTxOSize) * (
        utxoEntrySizeWithoutVal + tokenBundleSize
    )

    if minAda > result:
        result = minAda

    return result


def sign_tx(tx_file, signing_keys_list, output_fname="tx.signed", cwd=None):
    """Witnesses are the number of keys that will be signing the transaction.

    Examples:
    - at least "payment.skey" - usual transaction
    - "payment.skey", "stake.skey" - stake address registration
    - "cold.skey", "stake.skey", "payment.skey" - pool registration
    - "cold.skey", "payment.skey" - pool deregisration

    Runs on air-gapped offline machine. All signing and cert generation happens on offline machine
    """

    signing_keys_args = " ".join(
        ["--signing-key-file {}".format(skey) for skey in signing_keys_list]
    )

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

    result = cardano_cli.run(*list(filter(None, args)))

    if result["rc"] != 0:
        logger.error("Signing TX did not work.")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        sys.exit(1)

    return f"{cwd}/{output_fname}"


def get_tx_id(tx_file=None, tx_body_file=None):
    """Return transaction ID using either TX body file, or signed/final TX file

    One of two inputs is required.
    tx_body_file - raw transaction draft file, unsigned
    tx_file - signed transaction file. Has priority if both files provided.
    """

    if not tx_file and not tx_body_file:
        logger.error("Either 'tx_file' or 'tx_body_file' should be provided. None provided")
        sys.exit(1)

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
        sys.exit(1)

    tx_id = result["stdout"].strip()

    return tx_id


def submit_tx(signed_tx_f="tx.signed", cwd=None):
    """Submitting signed transaction to blockchain

    requires CARDANO_NODE_SOCKET env variable
    should run on online machine
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
        sys.exit(1)

    tx_id = get_tx_id(signed_tx_f)
    logger.info("Successfully submitted transaction %s", tx_id)

    return True


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
