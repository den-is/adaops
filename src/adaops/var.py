import os
import re
import sys
import json
import math
import time
import shutil
import subprocess
import urllib.request

from datetime import datetime, timedelta
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
        print("File doesn not exist:", fpath)
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

    cmd = f"cardano-cli query protocol-parameters {network}"

    process = subprocess.Popen(
        ["sh", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        params = json.loads(process.stdout.read())
        return params

    except JSONDecodeError as e:
        print('Was not able to get/parse protocol parameters')
        print(e)
        sys.exit(1)

    except ValueError as e:
        print('Was not able to get/parse protocol parameters')
        print(e)
        sys.exit(1)


def l2a(lovelace):
    '''Converts Lovelace into ADA

    Accepts Integer values only.
    Returns Float value
    '''
    if isinstance(lovelace, int):
        return float(lovelace / 1000000)


def a2l(ada):
    '''Converts ADA into Lovelace.

    Accepts Integer and Float values only.
    Returns Integer value.
    '''
    if isinstance(ada, (float, int)):
        return int(ada * 1000000)


def get_balances(address, user_utxo=None, network='--mainnet'):
    '''Get all TX hashes with their balance under given address

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
    '''

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

    output = {}

    filtered_utxos = address_balances_json.keys() # by default include all existing utxo hashes
    if user_utxo:
        filtered_utxos = [utxo for utxo in address_balances_json.keys() if utxo.startswith(user_utxo)]
        if not filtered_utxos:
            print(f'Provided by user UTXO hash "{user_utxo}" does not exist under the given address "{address}"')
        elif len(filtered_utxos) > 1:
            print('Balances query has returned more than 1 hashes. Probably different indexes of the same utxo.')
            print('Specify exact hash with index. Available hashes:', '\n'.join(filtered_utxos))

    for utxo in filtered_utxos:
        output[utxo] = {}
        output[utxo]['lovelace'] = address_balances_json[utxo]['value']['lovelace']
        if len(address_balances_json[utxo]['value'].keys()) > 1:
            output[utxo]['tokens'] = {}
            for key in address_balances_json[utxo]['value'].keys():
                if key != 'lovelace':
                    output[utxo]['tokens'][key] = address_balances_json[utxo]['value'][key]

    return output


def get_total_balance(address, network='--mainnet'):
    '''Get total balance for the given address, in Lovelaces

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.
    '''

    txs = get_balances(address=address, network=network)
    return sum([txs[tx]['lovelace'] for tx in txs])


def get_stake_rewards(stake_addr, network='--mainnet'):
    '''Get given stake address rewards balance

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.
    '''

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
        print(process_stdout_bytes.decode("utf-8"))
        print('Failed command was:', cmd)
        sys.exit(1)

    try:
        balances_json = json.loads(process_stdout_bytes)
    except (ValueError, JSONDecodeError) as e:
        print('Not able to get stake address rewards balance')
        print(e)
        sys.exit(1)

    return balances_json


def current_kes_period(current_slot, genesis_data):
    ''' Maybe just instead that function, that seems to simple and redundant,
    better to query genesis file and do math, directly in some python script?
    '''

    slots_per_period = genesis_data['slotsPerKESPeriod']

    return math.floor(current_slot/slots_per_period)


def get_current_tip(item='slot', retries=3, network='--mainnet'):
    '''Get current tip's slot of the blockchain
    By default return current slot.
    Possible options: 'slot', 'epoch', 'syncProgress', 'block', 'hash', 'era'

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH env var required
    '''

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
            print("Was not able to get the current tip")
            if decoded_output.startswith('MuxError'):
                print('Got not fatal error:', decoded_output)
                print('Going to retry after 3 seconds')
                time.sleep(3)
                continue
            else:
                print('Fatal error was:', decoded_output)
                sys.exit(1)
        else:
            exec_success = True

    output_dict = json.loads(decoded_output)
    if item not in output_dict.keys():
        items = ", ".join(output_dict.keys())
        print(f'Item "{item}" is not available. Available list of items: {items}. Exiting.')
        sys.exit(1)

    current_tip_item = output_dict[item]

    return current_tip_item


def calculate_current_epoch(genesis_data):
    """calculates current epoch based on system time and genesis file.
    Is offline method in opposite to getting current Tip of the network.
    genesis_data - JSON object containing Shelley genesis data.

    cardano start - 2017-09-23T21:44:51Z

    returns epoch - int
    """
    cardano_start_str = genesis_data.get('systemStart')
    epoch_len = int(genesis_data.get('epochLength', 0))

    if not cardano_start_str or not epoch_len:
        print("Not able to find \"systemStart\" or \"epochLength\" in genesis data. Make sure you have passed correct genesis file.")
        sys.exit(1)

    now = datetime.utcnow()
    cardano_start_dt = datetime.strptime(cardano_start_str, '%Y-%m-%dT%H:%M:%SZ')
    time_since_start = now - cardano_start_dt
    time_since_start_sec = time_since_start.total_seconds()

    return int(time_since_start_sec/epoch_len)


def time_until_next_epoch(genesis_data):
    """Calculates time until next epoch in seconds
    """
    cardano_start_str = genesis_data.get('systemStart')
    epoch_len = int(genesis_data.get('epochLength', 0))

    if not cardano_start_str or not epoch_len:
        print("Not able to find \"systemStart\" or \"epochLength\" in genesis data. Make sure you have passed correct genesis file.")
        sys.exit(1)

    now = datetime.utcnow()
    cardano_start_dt = datetime.strptime(cardano_start_str, '%Y-%m-%dT%H:%M:%SZ')
    time_since_start = now - cardano_start_dt
    time_since_start_sec = time_since_start.total_seconds()
    current_epoch = int(time_since_start_sec/epoch_len)

    next_epoch_in = epoch_len - (time_since_start_sec - current_epoch * epoch_len)

    return round(next_epoch_in, 1)


def calculate_epoch_date(epoch, genesis_data):
    """Returns datetime object for specific epoch. UTC
    epoch - int
    genesis_data - JSON
    """
    cardano_start_str = genesis_data.get('systemStart')
    epoch_len = int(genesis_data.get('epochLength', 0))

    if not cardano_start_str or not epoch_len:
        print("Not able to find \"systemStart\" or \"epochLength\" in genesis data. Make sure you have passed correct genesis file.")
        sys.exit(1)

    cardano_start_dt = datetime.strptime(cardano_start_str, '%Y-%m-%dT%H:%M:%SZ')

    total_epoch_seconds =  epoch * epoch_len

    epoch_date = cardano_start_dt + timedelta(seconds=total_epoch_seconds)

    return epoch_date


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
        print("Owner's Delegation cert creation didn't work")
        print(decoded_output)
        sys.exit(1)

    pool_metadata_hash = decoded_output.strip()

    return pool_metadata_hash


def download_meta(meta_url, dst_path):
    """Downloads Pool's metadata JSON file.

    Actually that can be URL to whatever valid JSON file - Not strictly checking Cardano metadata schema.
    """
    file_dst = Path(dst_path)

    # python 3.7 is missing "missing_ok" argument for unlink()
    if file_dst.exists():
        file_dst.unlink()

    with urllib.request.urlopen(meta_url) as response, open(file_dst, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

    valid_json_file = False
    with open(file_dst, 'r') as meta_f:
        try:
            json.load(meta_f)
            valid_json_file = True
        except ValueError as e:
            print('Downloaded file is not a valid JSON file.', e)

    if not valid_json_file:
        print('Exiting')
        sys.exit(1)

    return file_dst
