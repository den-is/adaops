import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from json import JSONDecodeError
from pathlib import Path

logger = logging.getLogger(__name__)


def check_file_exists(fpath):
    """Check if file exists and makes path absolute if required

    Args:
        fpath (str): Path to a file that needs to be checked.

    Returns:
        resolved: extended path to a file that is checked

        Exits with 1 if "FileNotFoundError" exception is raised
    """

    this_f = Path(fpath)

    try:
        resolved = this_f.resolve(strict=True)
        return resolved
    except FileNotFoundError:
        logger.error("File doesn not exist: %s", fpath)
        sys.exit(1)


def cmd_str_cleanup(s):
    """Remove excess whitespaces from command string"""

    no_newl = s.replace("\n", "")
    regex = re.compile(r"\s+", re.MULTILINE)
    return regex.sub(" ", no_newl)


def check_socket_env_var():
    """Checks if CARDANO_NODE_SOCKET_PATH env var is set.

    Required for running "online" commands that will query the network.
    For example to query address balance or network tip.
    """

    if not os.getenv("CARDANO_NODE_SOCKET_PATH"):
        logger.error("Not able to find CARDANO_NODE_SOCKET_PATH environment variable")
        logger.error(
            "Make sure that you are running on a node with active and fully synced cardano-node process."
        )
        logger.error(
            "If not satifies above statement make sure to at least set the CARDANO_NODE_SOCKET_PATH env variable."
        )
        sys.exit(1)

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
    """
    # TODO: check for negative and not int arguments
    return init_balance - sum([abs(arg) for arg in args])


def get_protocol_params(network="--mainnet"):
    """Get protocol parameters

    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.
    """

    check_socket_env_var()

    cmd = f"cardano-cli query protocol-parameters {network}"

    process = subprocess.Popen(
        ["sh", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        params = json.loads(process.stdout.read())
        return params

    except (JSONDecodeError, ValueError):
        logger.error("Was not able to get/parse protocol parameters", exc_info=1)
        sys.exit(1)


def l2a(lovelace):
    """Converts Lovelace into ADA

    Accepts Integer values only.
    Returns Float value
    """
    if isinstance(lovelace, int):
        return float(lovelace / 1000000)


def a2l(ada):
    """Converts ADA into Lovelace.

    Accepts Integer and Float values only.
    Returns Integer value.
    """
    if isinstance(ada, (float, int)):
        return int(ada * 1000000)


def get_balances(address, user_utxo=None, network="--mainnet"):
    """Get all TX hashes with their balance under given address

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.
    Returns tuple of hashes and their balances

    Example output:
    {'utxo_hash1#1': {'lovelace': 1000000000},
     'utxo_hash2#0': {'lovelace': 979279256,
                      'tokens': {'policy_id_1': {'SecondTesttoken': 9995000,
                                                 'Testtoken': 9999996
                                                }
                                }
                     }
    }
    """

    check_socket_env_var()

    cmd = f"cardano-cli query utxo --address {address} {network} --out-file /dev/stdout"

    process = subprocess.Popen(
        ["sh", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    process.wait()
    process_rc = process.returncode

    process_stdout_bytes = process.stdout.read()

    if process_rc != 0:
        logger.error("Not able to get address balances")
        logger.error(process_stdout_bytes.decode("utf-8"))
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        logger.error("Exiting")
        sys.exit(1)

    try:
        address_balances_json = json.loads(process_stdout_bytes)
    except (JSONDecodeError, ValueError):
        logger.error("Not able to parse address balances JSON", exc_info=1)
        sys.exit(1)

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
                "Balances query has returned more than 1 hashes. Probably different indexes of the same utxo."
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


def get_total_balance(address, network="--mainnet"):
    """Get total balance for the given address, in Lovelaces

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.
    """

    txs = get_balances(address=address, network=network)
    return sum([txs[tx]["lovelace"] for tx in txs])


def get_stake_rewards(stake_addr, network="--mainnet"):
    """Get given stake address rewards balance

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.
    """

    check_socket_env_var()

    cmd = f"cardano-cli query stake-address-info --address {stake_addr} {network}"

    process = subprocess.Popen(
        ["sh", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    process.wait()
    process_rc = process.returncode
    process_stdout_bytes = process.stdout.read()

    if process_rc != 0:
        logger.error(process_stdout_bytes.decode("utf-8"))
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    try:
        balances_json = json.loads(process_stdout_bytes)
    except (ValueError, JSONDecodeError):
        logger.error("Not able to parse stake address rewards balance JSON", exc_info=1)
        sys.exit(1)

    return balances_json


def current_kes_period(current_slot, genesis_data):
    """Returns Current KES period based on current tip of the network (slot).

    current_tip_slot/genesis_data['slotsPerKESPeriod']

    """

    slots_per_period = genesis_data["slotsPerKESPeriod"]

    return math.floor(current_slot / slots_per_period)


def get_current_tip(item="slot", retries=3, network="--mainnet"):
    """Get current tip's slot of the blockchain
    By default return current slot.
    Possible options: 'slot', 'epoch', 'syncProgress', 'block', 'hash', 'era'

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH env var required
    """

    cmd = f"cardano-cli query tip {network}"

    decoded_output = ""

    _retries = retries
    exec_success = False
    while not exec_success and _retries > 0:
        _retries -= 1
        process = subprocess.Popen(
            ["sh", "-c", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        process.wait()
        process_rc = process.returncode

        process_stdout_bytes = process.stdout.read()
        decoded_output = process_stdout_bytes.decode("utf-8")

        if process_rc != 0:
            logger.warning("Was not able to get the current tip")
            if decoded_output.startswith("MuxError"):
                logger.warning("Got not fatal error: %s", decoded_output)
                logger.warning("Going to retry after 3 seconds")
                time.sleep(3)
                continue
            else:
                logger.error("Fatal error was:", decoded_output)
                sys.exit(1)
        else:
            exec_success = True

    response_dict = json.loads(decoded_output)
    response_keys = list(response_dict.keys())
    response_keys.append("all")
    if item not in response_keys:
        items = ", ".join(response_keys)
        logger.error(
            'Item "%s" is not available. Available list of items: %s. Exiting.', item, items
        )
        sys.exit(1)

    if item != "all":
        current_tip_item = response_dict[item]
    else:
        current_tip_item = response_dict

    return json.dumps(current_tip_item)


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


def get_metadata_hash(metadata_f, cwd=None):

    metadata_json = {}
    with open(metadata_f) as json_file:
        metadata_json = json.load(json_file)

    if not metadata_json:
        logger.error("Was not able to find pool metadata in file: %s", metadata_f)
        sys.exit(1)

    ticker_re = re.compile(r"^([A-Z0-9]){3,5}$")
    re_check = ticker_re.search(metadata_json["ticker"])
    if not re_check:
        logger.error(
            "Ticker does not match patter: 3-5 chars long, A-Z and 0-9 characters only. Got %s",
            metadata_json["ticker"],
        )
        sys.exit(1)

    if len(metadata_json["description"]) > 255:
        logger.error(
            "Pool description field value exceeds 255 characters. Length: %d",
            len(metadata_json["description"]),
        )
        sys.exit(1)

    cmd = f"cardano-cli stake-pool metadata-hash --pool-metadata-file {metadata_f}"

    process = subprocess.Popen(
        ["sh", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )

    process.wait()
    process_rc = process.returncode
    process_stdout_bytes = process.stdout.read()
    decoded_output = process_stdout_bytes.decode("utf-8")

    if process_rc != 0:
        logger.error("Was not able to generate metadata hash")
        logger.error(decoded_output)
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    pool_metadata_hash = decoded_output.strip()

    return pool_metadata_hash


def download_meta(meta_url, dst_path):
    """Downloads Pool's metadata JSON file.

    Actually that can be URL to whatever valid JSON file.
    Not strictly checking Cardano metadata schema.
    """
    file_dst = Path(dst_path)

    # python 3.7 is missing "missing_ok" argument for unlink()
    if file_dst.exists():
        file_dst.unlink()

    with urllib.request.urlopen(meta_url) as response, open(file_dst, "wb") as out_file:
        shutil.copyfileobj(response, out_file)

    valid_json_file = False
    with open(file_dst, "r") as meta_f:
        try:
            json.load(meta_f)
            valid_json_file = True
        except ValueError:
            logger.error("Downloaded file is not a valid JSON file.", exc_info=1)

    if not valid_json_file:
        logger.error("Got invalid JSON file. Exiting")
        sys.exit(1)

    return file_dst
