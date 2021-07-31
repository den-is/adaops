import os
import re
import sys
import json
import math
import subprocess

from pathlib import Path
from json import JSONDecodeError


def check_file_exists(fpath):
    '''Check if file exists and makes path absolute if required

    Args:
      fpath (str): Path to a file that needs to be checked.

    Returns:
      resolved: extended path to a file that is checked

      Exits with 1 if "FileNotFoundError" exception is raised
    '''

    this_f = Path(fpath)

    try:
        resolved = this_f.resolve(strict=True)
        return resolved
    except FileNotFoundError:
        print("File not exists:", fpath)
        sys.exit(1)


def check_socket_env_var():
    '''Checks if CARDANO_NODE_SOCKET_PATH env var is set.

    Required for running "online" commands that will query the network.
    If doesn't exist cardano-cli will not work for online commands. For example quering address UTXO.
    '''

    if not os.getenv('CARDANO_NODE_SOCKET_PATH'):
        print('Not able to find CARDANO_NODE_SOCKET_PATH environment variable.')
        print('Make sure that you are running on a node with active and fully synced cardano-node process.')
        print('If not satifies above statement make sure to at least set the CARDANO_NODE_SOCKET_PATH env variable.')
        sys.exit(1)

    return True


def change_calc(init_balance, *args):
    '''Calculates the change to return.

    Accepts initial balance and arbitrary number of fees to deduct
    Examples:
        Stake address registration: init_balance - stake_address_registration_deposit - tx_fee
        Pool registration: init_balance - stakePoolDeposit - tx_fee
        Pool Retirement certificate registration: init_balance - tx_fee
        Send money to someone and pay fee: init_balance - send_amount_lovelace - tx_fee
        Also helpfull when you want to migrate ALL funds to some address and pay tx fee: init_balance - tx_fee = amount to migrate
    '''
    # TODO: check for negative and not int arguments
    return init_balance - sum([abs(arg) for arg in args])


def get_protocol_params(network='--mainnet'):
    '''Get protocol parameters

    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.
    '''

    check_socket_env_var()

    cmd = [
        "sh",
        "-c",
        f"cardano-cli query protocol-parameters {network}"
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        params = json.loads(process.stdout.read())
    except JSONDecodeError as e:
        print('Was not able to get protocol parameters')
        print(e)
        sys.exit(1)
    except ValueError as e:
        print(e)
        sys.exit(1)

    return params


def lovelace2ada(lovelace):
    '''Converts Lovelace into ADA

    Accepts Integer values only.
    Returns Float value
    '''
    if isinstance(lovelace, int):
        return float(lovelace / 1000000)


def ada2lovelace(ada):
    '''Converts ADA into Lovelace.

    Accepts Integer and Float values only.
    Returns Integer value.
    '''
    if isinstance(ada, (float, int)):
        return int(ada * 1000000)


def get_balances(address, network='--mainnet'):
    '''Get all TX hashes with their balance under given address

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.
    Returns tuple of hashes and their balances
    '''

    cmd = [
        "sh",
        "-c",
        f"cardano-cli query utxo --address {address} {network} --out-file /dev/stdout"
    ]

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
        print(process_stdout_bytes.decode("utf-8"))
        print('Not able to get address balances. Exiting.')
        sys.exit(1)

    try:
        address_balances_json = json.loads(process_stdout_bytes)
    except JSONDecodeError as e:
        print(e)
        sys.exit(1)
    except ValueError as e:
        print(e)
        sys.exit(1)

    hashes = tuple({'hash': tx, 'balance': address_balances_json[tx]['value']['lovelace']} for tx in address_balances_json.keys())

    return hashes


def get_total_balance(address, network='--mainnet'):
    '''Get total balance for the given address, in Lovelaces

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.
    '''

    txs = get_balances(address=address, network=network)
    return sum([tx['balance'] for tx in txs])


def get_stake_rewards(stake_addr, network='--mainnet'):
    '''Get given stake address rewards balance

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.
    '''

    cmd = [
        "sh",
        "-c",
        f"cardano-cli query stake-address-info --address {stake_addr} {network}"
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=dict(os.environ, CARDANO_NODE_SOCKET_PATH="/opt/cardano/sockets/node.socket"),
    )

    try:
        balances_json = json.loads(process.stdout.read())
    except JSONDecodeError as e:
        print('Not able to get stake address rewards balance')
        print(e)
        sys.exit(1)
    except ValueError as e:
        print('Not able to get stake address rewards balance')
        print(e)
        sys.exit(1)

    return balances_json


def current_kes_period(current_slot, genesis_data):
    '''???????????
    probably not needed to lookup for a key in whole genesis data object.
    Maybe just receiving required numbers will be fine.
    ????????????
    '''

    slots_per_period = genesis_data['slotsPerKESPeriod']

    return math.floor(current_slot/slots_per_period)


def get_current_tip(network='--mainnet'):
    '''Get current tip's slot of the blockchain

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH env var required
    '''

    cmd = [
        "sh",
        "-c",
        f"cardano-cli query tip {network}"
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    process.wait()
    process_rc = process.returncode

    process_stdout_bytes = process.stdout.read()

    if process_rc != 0:
        print("Was not able to get the current tip")
        print(process_stdout_bytes.decode("utf-8"))
        sys.exit(1)

    current_slot = json.loads(process.stdout.read())['slot']

    return current_slot


def get_current_epoch(network='--mainnet'):
    '''Get current epoch

    CARDANO_NODE_SOCKET is required
    '''

    cmd = [
        "sh",
        "-c",
        f'''cardano-cli query tip {network}'''
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    process.wait()
    process_rc = process.returncode
    process_stdout_bytes = process.stdout.read()

    if process_rc != 0:
        print("Was not able to create pool deregistration cert")
        print(process_stdout_bytes.decode("utf-8"))
        sys.exit(1)

    return json.loads(process.stdout.read())['epoch']


def get_metadata_hash(metadata_f, cwd=None):

    metadata_json = {}
    with open(metadata_f) as json_file:
        metadata_json = json.load(json_file)

    if not metadata_json:
        print('Was not able to find pool metadata in file:', metadata_f)
        sys.exit(1)

    ticker_re = re.compile(r'^([A-Z0-9]){3,5}$')
    re_check = ticker_re.search(metadata_json['ticker'])
    if not re_check:
        print('Ticker does not match patter: 3-5 chars long, A-Z and 0-9 characters only', metadata_json['ticker'])
        sys.exit(1)

    if len(metadata_json['description']) > 255:
        print('Pool description field value exceeds 255 characters. Chars:', len(metadata_json['description']))
        sys.exit(1)

    cmd = [
        "sh",
        "-c",
        f"cardano-cli stake-pool metadata-hash --pool-metadata-file {metadata_f}"
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )

    process.wait()
    process_rc = process.returncode

    if process_rc != 0:
        print("Owner's Delegation cert creation didn't work")
        stdout_bytes = process.stdout.read()
        print(stdout_bytes.decode("utf-8"))
        sys.exit(1)

    exe_metadata_hash_bytes = process.stdout.read()
    pool_metadata_hash = exe_metadata_hash_bytes.decode("utf-8").strip()

    return pool_metadata_hash
