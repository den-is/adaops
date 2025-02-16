import decimal
import json
import logging
import math
import os
import re
import shutil
import time
import urllib.request
from binascii import hexlify, unhexlify
from collections import defaultdict
from json import JSONDecodeError
from pathlib import Path

from adaops import NET_ARG, cardano_cli
from adaops.exceptions import BadCmd, NodeDown

logger = logging.getLogger(__name__)


def check_file_exists(fpath) -> Path:
    """Check if file exists and makes path absolute if required

    Args:
        fpath (str): Path to a file that needs to be checked.

    Returns:
        resolved: extended path to a file that is checked

        Exits with 1 if "FileNotFoundError" exception is raised

    Raises:
        FileNotFoundError: If file does not exist
    """

    this_f = Path(fpath)

    try:
        resolved = this_f.resolve(strict=True)
        return resolved
    except FileNotFoundError:
        logger.error("File doesn not exist: %s", fpath)
        raise


def cmd_str_cleanup(s) -> str:
    """Remove excess whitespaces from command string"""

    if isinstance(s, list):
        s = " ".join(s)

    s = s.removeprefix("sh -c ")

    no_newl = s.replace("\n", "")
    regex = re.compile(r"\s+", re.MULTILINE)
    return regex.sub(" ", no_newl)


def check_socket_env_var() -> bool:
    """Checks if CARDANO_NODE_SOCKET_PATH env var is set and indicated file exists.

    Existing socket file does not mean that cardano-node is running and fully synced.

    Required for running "online" commands that will query the network.
    For example to query address balance or network tip.

    Raises:
        RuntimeError: If CARDANO_NODE_SOCKET_PATH env var is not set or file does not exist
        RuntimeError: If CARDANO_NODE_SOCKET_PATH is set, but file does not exist
    """

    socket_path_val = os.getenv("CARDANO_NODE_SOCKET_PATH")
    if not socket_path_val:
        logger.error("CARDANO_NODE_SOCKET_PATH ENV variable is absent or has no value assigned")
        logger.error(
            "Make sure that you are running on a machine with an active and fully synced cardano-node process"  # noqa
        )
        raise RuntimeError(
            "CARDANO_NODE_SOCKET_PATH ENV variable is absent or has no value assigned"
        )

    if socket_path_val:
        if not Path(socket_path_val).exists():
            logger.error(
                "CARDANO_NODE_SOCKET_PATH is set, but file does not exist: %s", socket_path_val
            )
            raise RuntimeError(
                f"CARDANO_NODE_SOCKET_PATH is set, but file does not exist: {socket_path_val}"
            )

    return True


def change_calc(init_balance, *args):
    """Calculates the change to return.

    Accepts initial balance and arbitrary number of fees to deduct
    Examples:
        Stake address registration: init_balance - stake_address_registration_deposit - tx_fee
        Pool registration: init_balance - stakePoolDeposit - tx_fee
        Pool Retirement certificate registration: init_balance - tx_fee
        Send money to someone and pay fee: init_balance - send_amount_lovelace - tx_fee
        Also helpfull when you want to migrate ALL funds to some address and pay tx fee: init_balance - tx_fee = amount to migrate
    """  # noqa
    # TODO: check for negative and not int arguments
    return init_balance - sum([abs(arg) for arg in args])


def get_protocol_params():
    """Get protocol parameters

    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.

    Raises:
        RuntimeError: If was not able to get/parse protocol parameters
    """  # noqa

    check_socket_env_var()

    args = ["query", "protocol-parameters", *NET_ARG]

    result = cardano_cli.run(*args)

    try:
        params = json.loads(result["stdout"])
        return params

    except (JSONDecodeError, ValueError) as err:
        logger.error("Was not able to get/parse protocol parameters", exc_info=True)
        raise RuntimeError("Was not able to get/parse protocol parameters") from err


def l2a(lovelace):
    """Converts Lovelace into ADA

    Accepts Integer values only.
    Returns Float value
    """
    if isinstance(lovelace, int | float | decimal.Decimal):
        return float(lovelace / 1000000)


def a2l(ada):
    """Converts ADA into Lovelace.

    Accepts Integer and Float values only.
    Returns Integer value.
    """
    if isinstance(ada, float | int | decimal.Decimal):
        return int(ada * 1000000)


def a2h(ascii_s) -> str:
    """Converts ASCII string into hex representation string"""
    return hexlify(ascii_s.encode()).decode()


def h2a(hex_s) -> str:
    """Converts hex string into ASCII representation string"""

    if len(hex_s) % 2 != 0:
        logger.warning(
            'Hex string "%s" might be broken, as it contains odd number of characters %d',
            hex_s,
            len(hex_s),
        )

    return unhexlify(hex_s).decode()


def validate_utxo(utxo: str) -> bool:
    """Validates whether the given string is a correctly formatted Cardano UTXO.
    Input format should be `utxo#idx`
    """
    UTXO_REGEX = re.compile(r"^[0-9a-fA-F]{64}#[0-9]+$")
    return bool(UTXO_REGEX.fullmatch(utxo))


def query_utxo(utxo):
    """Query UTXO balance

    Args:
        utxo (str): UTXO to query in `utxo#idx` format

    Raises:
        ValueError - If provided UTXO is not in a correct format `utxo#idx`
        BadCmd - If was not able to query UTXO and cardano-cli did not return 0 exit code
    """
    check_socket_env_var()

    if not validate_utxo(utxo):
        raise ValueError(f"Provided UTXO '{utxo}' is not in a correct format `utxo#idx`")

    args = ["query", "utxo", "--tx-in", utxo, *NET_ARG, "--output-json"]
    result = cardano_cli.run(*args)
    if result["rc"] != 0:
        logger.error("Was not able to query UTXO %s", utxo)
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to query UTXO", cmd=cmd_str_cleanup(result["cmd"]))

    try:
        utxo_balance = json.loads(result["stdout"])
    except (JSONDecodeError, ValueError) as err:
        logger.error("Not able to parse UTXO balances JSON", exc_info=True)
        raise ValueError("Not able to parse UTXO balances JSON") from err

    output = {
        utxo: {
            "lovelace": 0,
            "tokens": {},
        }
    }

    if utxo_balance:

        # get lovelace balance
        output[utxo]["lovelace"] = utxo_balance[utxo]["value"]["lovelace"]

        # get tokens balance
        if len(utxo_balance[utxo]["value"].keys()) > 1:
            output[utxo]["tokens"] = {}
            for key in utxo_balance[utxo]["value"].keys():
                if key != "lovelace":
                    output[utxo]["tokens"][key] = utxo_balance[utxo]["value"][key]

    return output


def get_balances(address, user_utxo=None) -> dict:
    """Get all TX hashes with their balance under given address

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.
    Returns tuple of hashes and their balances

    Example:
        ```
        {
            'utxo_hash1#1': {
                'lovelace': 1000000000
            },
            'utxo_hash2#0': {
                'lovelace': 979279256,
                'tokens': {
                    'policy_id_1': {
                        'token1_hexname': 9995000,
                        'another_token_hexname': 9999996
                    }
                }
            }
        }
        ```

    Raises:
        BadCmd: If was not able to get address balances
        ValueError: If was not able to parse address balances JSON
    """  # noqa

    check_socket_env_var()

    args = ["query", "utxo", "--address", address, *NET_ARG, "--output-json"]

    result = cardano_cli.run(*args)

    if result["rc"] != 0:
        logger.error("Not able to get address balances")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to get address balances", cmd=cmd_str_cleanup(result["cmd"]))

    try:
        address_balances_json = json.loads(result["stdout"])
    except (JSONDecodeError, ValueError) as err:
        logger.error("Not able to parse address balances JSON", exc_info=True)
        raise ValueError("Not able to parse address balances JSON") from err

    output = {}

    filtered_utxos = address_balances_json.keys()  # by default include all existing utxo hashes
    if user_utxo:
        filtered_utxos = [
            utxo for utxo in address_balances_json.keys() if utxo.startswith(user_utxo)
        ]
        if not filtered_utxos:
            logger.error(
                'Provided by user UTXO hash "%s" does not exist under the given address "%s"',
                user_utxo,
                address,
            )
        elif len(filtered_utxos) > 1:
            logger.warning(
                "Balances query has returned more than 1 hashes. Probably different indexes of the same utxo."  # noqa
            )
            logger.warning(
                "Specify exact hash with index. Available hashes:\n%s", "\n".join(filtered_utxos)
            )

    for utxo in filtered_utxos:
        output[utxo] = {}
        output[utxo]["lovelace"] = address_balances_json[utxo]["value"]["lovelace"]
        if len(address_balances_json[utxo]["value"].keys()) > 1:
            output[utxo]["tokens"] = {}
            for key in address_balances_json[utxo]["value"].keys():
                if key != "lovelace":
                    output[utxo]["tokens"][key] = address_balances_json[utxo]["value"][key]

    return output


def combine_utxo_balance(*dicts: dict) -> dict:
    """Merges Token assets comming from multiple UTXOs. Works with one UTXO too.

    Args:
        *dicts - arbitrary number of dictionaries with assets format {policy1:{token1: amount, ...}, ....}
                 as returned by query_utxo() or get_balances()

    Returns:
        dict - combined balance dict in format {"lovelace", total-int, "tokens" :{"policyA": {"tokenY": int_amount}}}
    Example:
        ```
        # Example usage:
        dict1 = {
            "lovelace": 5000000,
            "tokens":{
                "policy1": {"tokenA": 1000, "tokenB": 500},
                "policy2": {"tokenC": 200}
            }
        }

        dict2 = {
            "lovelace": 2700000,
            "tokens":{
                "policy1": {"tokenA": 300, "tokenB": 200, "tokenD": 100},
                "policy3": {"tokenE": 700}
            }
        }

        merged_balance = combine_utxo_balance(dict1, dict2)

        print(merged_balance)
        # output
        # {'lovelace': 7700000,
        # 'tokens': {'policy1': {'tokenA': 1300, 'tokenB': 700, 'tokenD': 100},
        #             'policy2': {'tokenC': 200},
        #             'policy3': {'tokenE': 700}}}
        ```
    """  # noqa

    merged = defaultdict(lambda: defaultdict(int))
    total_lovelace = 0

    for d in dicts:
        if "lovelace" in d:
            total_lovelace += d["lovelace"]

        if "tokens" in d:
            for policy, tokens in d["tokens"].items():
                for token, amount in tokens.items():
                    merged[policy][token] += amount

    return {
        "lovelace": total_lovelace,
        "tokens": {k: dict(v) for k, v in merged.items()},
    }


def get_total_balance(address) -> int:
    """Get total balance for the given address, in Lovelaces

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.
    """  # noqa

    txs = get_balances(address=address)
    return sum([txs[tx]["lovelace"] for tx in txs])


def get_utxo_with_enough_balance(utxos_map, amount) -> str | None:
    """Receives map of UTXos, output from get_balances(addr) and returns singe UTXo with balance more or equal to given amount"""  # noqa
    utxos = list(utxos_map.keys())
    utxo = utxos.pop()

    while utxos_map[utxo]["lovelace"] < amount:
        if not utxos:
            logger.warning("Provided address has not a single UTXO with enough balance")
            logger.warning(
                "You might want to join multiple UTXOs in input-list or try a different address"
            )
            return None

        utxo = utxos.pop()

    return utxo


def get_stake_rewards(stake_addr) -> dict:
    """Get rewards balance of the specified stake_addr

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.

    Raises:
        BadCmd: If was not able to get rewards balance for stake address
        ValueError: If was not able to parse stake address rewards balance JSON
    """  # noqa

    check_socket_env_var()

    args = [
        "query",
        "stake-address-info",
        "--address",
        stake_addr,
        *NET_ARG,
    ]

    result = cardano_cli.run(*args)

    if result["rc"] != 0:
        logger.error("Was not able to get rewards balance for stake address")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to get rewards balance for stake address", cmd=result["cmd"])

    try:
        balances_json = json.loads(result["stdout"])
    except (ValueError, JSONDecodeError) as err:
        logger.error("Not able to parse stake address rewards balance JSON:", exc_info=True)
        logger.error(result["stdout"])
        raise ValueError("Not able to parse stake address rewards balance JSON") from err

    return balances_json


def get_current_tip(item="slot", retries=3, return_json=False) -> dict | str | int | float:
    """Get current tip's slot of the blockchain
    By default return current slot.
    Possible "item" options:
    - 'all'
    - 'slot'
    - 'epoch'
    - 'syncProgress'
    - 'block'
    - 'hash'
    - 'era'
    - 'slotInEpoch'
    - 'slotsToEpochEnd'
    return_json - return JSON string. default False

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH env var required

    Raises:
        NodeDown: cardano-node is OFFLINE or the service LOADING is in the progress
        BadCmd: If was not able to get the current tip
        KeyError: If requested item is not available
    """

    args = ["query", "tip", *NET_ARG]

    result = {}

    _retries = retries
    exec_success = False
    while not exec_success and _retries > 0:
        _retries -= 1

        result = cardano_cli.run(*args)

        if result["rc"] != 0:
            logger.warning("Was not able to get the current tip")
            err_msg = result["stderr"].strip()
            if err_msg.startswith("MuxError"):
                logger.warning("Got not fatal error: %s", err_msg)
                logger.warning("Going to retry after 3 seconds")
                time.sleep(3)
                continue
            elif (
                err_msg
                == "cardano-cli: Network.Socket.connect: <socket: 11>: does not exist (Connection refused)"  # noqa
            ):
                # NOTE: actually several other online commands might throw this error if node is offline # noqa
                # need to centralize that somehow for online commands
                # move that test and loging into wrapper.run?
                logger.error("cardano-node is OFFLINE or the service LOADING is in the progress")
                logger.error("Fatal error was: %s", err_msg)
                raise NodeDown
            else:
                logger.error("Fatal error was: %s", err_msg)
                logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
                raise BadCmd("Was not able to get the current tip", cmd=result["cmd"])
        else:
            exec_success = True

    response_dict = json.loads(result["stdout"])

    try:
        if item == "all":
            current_tip_item = response_dict
        else:
            current_tip_item = response_dict[item]
    except KeyError:
        response_keys = list(response_dict.keys())
        logger.error(
            'Item "%s" is not available. Available list of items: %s. Exiting.',
            item,
            ", ".join(["all", *response_keys]),
        )
        raise

    if return_json:
        return json.dumps(current_tip_item)

    return current_tip_item


def current_kes_period(current_slot, genesis_data) -> int:
    """Returns Current KES period based on current tip of the network (slot).
    Requires Shelley genesis data file

    current_tip_slot/genesis_data['slotsPerKESPeriod']

    """

    slots_per_period = genesis_data["slotsPerKESPeriod"]

    return math.floor(current_slot / slots_per_period)


def expected_slot(genesis_data, byron_genesis_data):
    """Returns expected tip slot for post Byron eras.
    Helps to determine cardano-node sync-status and catch sync issues.
    """

    # TODO: move that to constants or calculate automatically
    shelley_start_epoch = 208

    byron_slot_length = byron_genesis_data.get("blockVersionData").get("slotDuration") / 1000
    byron_epoch_length = byron_genesis_data.get("protocolConsts").get("k") * 10
    byron_start = byron_genesis_data.get("startTime")

    slot_length = int(genesis_data.get("slotLength"), 1)

    byron_end = byron_start + shelley_start_epoch * byron_epoch_length * byron_slot_length
    byron_slots = shelley_start_epoch * byron_epoch_length

    now_sec_since_epoch = int(time.time())

    expected_slot = byron_slots + (now_sec_since_epoch - byron_end) / slot_length

    return expected_slot


def get_metadata_hash(metadata_f, cwd=None) -> str:
    """Generates hash for pool's metadata JSON file.

    Raises:
        RuntimeError: Was not able to find pool metadata in file
        ValueError: Ticker does not match patter: 3-5 chars long, A-Z and 0-9 characters only
        ValueError: Pool description field value exceeds 255 characters
        BadCmd: Was not able to generate hash for pool's metadata
    """

    metadata_json = {}

    checked_file = check_file_exists(metadata_f)
    with open(checked_file) as json_file:
        metadata_json = json.load(json_file)

    if not metadata_json:
        logger.error("Was not able to find pool metadata in file: %s", metadata_f)
        raise RuntimeError("Was not able to find pool metadata in file.")

    ticker_re = re.compile(r"^([A-Z0-9]){3,5}$")
    re_check = ticker_re.search(metadata_json["ticker"])
    if not re_check:
        logger.error(
            "Ticker does not match patter: 3-5 chars long, A-Z and 0-9 characters only. Got %s",
            metadata_json["ticker"],
        )
        raise ValueError(
            f"Ticker does not match patter: 3-5 chars long, A-Z and 0-9 characters only. Got {metadata_json['ticker']}"  # noqa
        )

    if len(metadata_json["description"]) > 255:
        logger.error(
            "Pool description field value exceeds 255 characters. Length: %d",
            len(metadata_json["description"]),
        )
        raise ValueError(
            f"Pool description field value exceeds 255 characters. Length: {len(metadata_json['description'])}"  # noqa
        )

    args = [
        "stake-pool",
        "metadata-hash",
        "--pool-metadata-file",
        metadata_f,
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Was not able to generate hash for pool's metadata")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to generate hash for pool's metadata", cmd=result["cmd"])

    pool_metadata_hash = result["stdout"].strip()

    return pool_metadata_hash


def download_meta(meta_url, dst_path) -> Path:
    """Downloads Pool's metadata JSON file.

    Actually that can be URL to whatever valid JSON file.
    Not strictly checking Cardano metadata schema.

    Raises:
        ValueError: Downloaded file is not a valid JSON file.
    """
    file_dst = Path(dst_path)

    # python 3.7 is missing "missing_ok" argument for unlink()
    if file_dst.exists():
        file_dst.unlink()

    with urllib.request.urlopen(meta_url) as response, open(file_dst, "wb") as out_file:
        shutil.copyfileobj(response, out_file)

    with open(file_dst) as meta_f:
        try:
            _ = json.load(meta_f)
        except ValueError as err:
            logger.error("Downloaded file is not a valid JSON file.", exc_info=True)
            raise ValueError("Downloaded file is not a valid JSON file.") from err

    return file_dst
