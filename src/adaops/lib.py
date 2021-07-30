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
        print('Not able to find CARDANO_NODE_SOCKET_PATH environment variable.\nMake sure to set it before running the script.')
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
        # env=dict(os.environ, CARDANO_NODE_SOCKET_PATH="/opt/cardano/sockets/node.socket"),
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
        print('Not able to get address balances')
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


def get_stake_rewards(stake_addr, network='--mainnet'):
    '''Get given stake address rewards

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


def get_total_balance(address, network='--mainnet'):
    '''Get total balance for the given address, in Lovelaces

    Runs on online machine.
    CARDANO_NODE_SOCKET_PATH environment variable should be set and pointing to active cardano-node socket.
    '''

    txs = get_balances(address=address, network=network)
    return sum([tx['balance'] for tx in txs])


def get_pool_id(cold_vkey='cold.vkey', cwd=None):
    '''Returns Pool's ID
    '''

    if cwd:
        checked_f = check_file_exists("{cwd}/{cold_vkey}")
    else:
        checked_f = check_file_exists(cold_vkey)

    cmd = [
        "sh",
        "-c",
        f"cardano-cli stake-pool id --cold-verification-key-file {checked_f} --output-format hex"
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )

    process.wait()
    process_rc = process.returncode

    process_stdout_bytes = process.stdout.read()

    if process_rc != 0:
        print(process_stdout_bytes.decode("utf-8"))
        print('Not able to get pool ID')
        sys.exit(1)

    return process_stdout_bytes.decode("utf-8").strip()


def current_kes_period(current_slot, genesis_data):
    '''???????????
    probably not needed to lookup for a key in whole genesis data object.
    Maybe just receiving required numbers will be fine.
    ????????????
    '''

    slots_per_period = genesis_data['slotsPerKESPeriod']

    return math.floor(current_slot/slots_per_period)


def get_pool_stake_snapshot(pool_id, network='--mainnet'):
    '''Get active pool stake snapshot.

    CARDANO_NODE_SOCKET_PATH env var required
    '''

    cmd = [
        "sh",
        "-c",
        f"cardano-cli query stake-snapshot --stake-pool-id {pool_id} {network}"
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=dict(os.environ, CARDANO_NODE_SOCKET_PATH="/opt/cardano/sockets/node.socket"),
    )

    try:
        output = json.loads(process.stdout.read())
    except JSONDecodeError as e:
        print(e)
        sys.exit(1)
    except ValueError as e:
        print(e)
        sys.exit(1)

    return output


def get_pool_params(pool_id, network='--mainnet'):
    '''Get active pool parameters.

    CARDANO_NODE_SOCKET_PATH env var required
    '''

    cmd = [
        "sh",
        "-c",
        f"cardano-cli query pool-params --stake-pool-id {pool_id} {network}"
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=dict(os.environ, CARDANO_NODE_SOCKET_PATH="/opt/cardano/sockets/node.socket"),
    )

    try:
        output = json.loads(process.stdout.read())
    except JSONDecodeError as e:
        print(e)
        sys.exit(1)
    except ValueError as e:
        print(e)
        sys.exit(1)

    return output


def get_current_tip(network='--mainnet'):
    ''' Query the tip of the blockchain

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

    if process_rc != 0:
        print("Was not able to get the current tip")
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

    if process_rc != 0:
        print("Was not able to create pool deregistration cert")
        print(process.stdout.read())
        sys.exit(1)

    return json.loads(process.stdout.read())['epoch']


def generate_node_cold_keys(name_prefix='cold', cwd=None):
    ''' Generates Cold/Node key pair

    Runs on air-gapped offline node
    returns tuple of two keys and counter
    '''

    cmd = [
        "sh",
        "-c",
        f'''cardano-cli node key-gen \
            --cold-verification-key-file {name_prefix}.vkey \
            --cold-signing-key-file {name_prefix}.skey \
            --operational-certificate-issue-counter-file {name_prefix}.counter'''
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )
    process.wait()
    process_rc = process.returncode

    proc_stdout_bytes = process.stdout.read()
    print(proc_stdout_bytes.decode('utf-8'))

    if process_rc != 0:
        print("Was not able to generate node's Cold key pair")
        sys.exit(1)

    return (f'{cwd}/{name_prefix}.vkey', f'{cwd}/{name_prefix}.skey', f'{cwd}/{name_prefix}.counter')


def generate_node_vrf_keys(name_prefix='vrf', cwd=None):
    ''' Generates VRF key pair

    Runs on air-gapped offline node
    returns tuple of two keys
    '''

    cmd = [
        "sh",
        "-c",
        f'''cardano-cli node key-gen-VRF \
            --verification-key-file {name_prefix}.vkey \
            --signing-key-file {name_prefix}.skey'''
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )
    process.wait()
    process_rc = process.returncode

    proc_stdout_bytes = process.stdout.read()
    print(proc_stdout_bytes.decode('utf-8'))

    if process_rc != 0:
        print("Was not able to generate node's VRF key pair")
        sys.exit(1)

    return (f'{cwd}/{name_prefix}.vkey', f'{cwd}/{name_prefix}.skey')


def generate_node_kes_keys(name_prefix='kes', cwd=None):
    ''' Generates KES key pair

    Don't forget to reginerate it every 90 days (calculate actual expiration based on genesis file)

    Runs on air-gapped offline node
    returns tuple of two keys
    '''

    cmd = [
        "sh",
        "-c",
        f'''cardano-cli node key-gen-KES \
            --verification-key-file {name_prefix}.vkey \
            --signing-key-file {name_prefix}.skey'''
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )
    process.wait()
    process_rc = process.returncode

    proc_stdout_bytes = process.stdout.read()
    print(proc_stdout_bytes.decode('utf-8'))

    if process_rc != 0:
        print("Was not able to generate node's KES key pair")
        sys.exit(1)

    return (f'{cwd}/{name_prefix}.vkey', f'{cwd}/{name_prefix}.skey')


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


def generate_node_cert(kes_vkey, cold_skey, cold_counter, kes_period, output_name='node.cert', cwd=None):
    '''Generate Node Operational certificate
    requires renewal as soon as KES key pair is renewed

    kes_vkey - path to kes.vkey
    cold_skey - path to cold.skey
    cold_counter - path to cold.counter
    kes_period - integer, current KES period
    '''

    cmd = [
        "sh",
        "-c",
        f'''cardano-cli node issue-op-cert \
            --kes-verification-key-file {kes_vkey} \
            --cold-signing-key-file {cold_skey} \
            --operational-certificate-issue-counter {cold_counter} \
            --kes-period {kes_period} \
            --out-file {output_name}'''
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )

    process.wait()
    process_rc = process.returncode

    process_stdout_bytes = process.stdout.read()

    if process_rc != 0:
        print("Was not able to generate node cert")
        print(process_stdout_bytes.decode('utf-8'))
        sys.exit(1)

    return f'{cwd}/{output_name}'


def generate_stake_reg_cert(output_name='stake.cert', stake_vkey='stake.vkey', cwd=None):
    '''Generate stake address registration certificate

    Runs on an air-gapped offline machine
    '''

    cmd = [
        "sh",
        "-c",
        f'''cardano-cli stake-address registration-certificate \
            --stake-verification-key-file {stake_vkey} \
            --out-file {output_name}'''
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
        print("Was not able to create stake registration cert")
        print(process.stdout.read())
        sys.exit(1)

    return f'{cwd}/{output_name}'


def generate_delegation_cert(output_name, owner_stake_vkey, cold_vkey, cwd=None):
    ''' Generations stake delegation certificate for the owner

    Runs on an air-gapped offline machine
    '''
    cmd = [
        "sh",
        "-c",
        f'''cardano-cli stake-address delegation-certificate \
            --stake-verification-key-file {owner_stake_vkey} \
            --cold-verification-key-file {cold_vkey} \
            --out-file {output_name}'''
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
        sys.exit(1)

    return f'{cwd}/{output_name}'


def generate_pool_reg_cert(cold_vkey,
                            vrf_vkey,
                            pledge_amt,
                            pool_cost,
                            margin,
                            reward_stake_vkey,
                            owners_stake_vkeys_list,
                            metadata_hash,
                            metadata_url,
                            relay_port,
                            relays_ipv4_list = [],
                            relays_dns_list = [],
                            network='--mainnet',
                            cwd=None,
                            output_fname='pool-registration.cert'
                            ):

    '''There might be multiple pool-owner-stake-verification keys
    owners_vkeys - list of string paths to Stake VKEYs. Generate into appropriate argument internaly.

    All relays should be running on the same port.

    relays_ipv4_list - list of string in format 'pool_ipv4:port'

    Runs on an air-gapped offline machine
    '''

    if len(metadata_url) > 64:
        print('Metadata URL is longer than 64 characters', metadata_url)

    if not isinstance(owners_stake_vkeys_list, list):
        print('owners_stake_vkeys - should be a list of strings with full path to owner stake verification keys')
        sys.exit(1)

    owners_stake_vkeys_args = ' '.join(['--pool-owner-stake-verification-key-file {}'.format(vkey_path) for vkey_path in owners_stake_vkeys_list])
    print('owner_keys_in_cert', owners_stake_vkeys_args)

    if not relays_dns_list and not relays_ipv4_list:
        print('Neither relays_dns_list or relays_ipv4_list supplied')
        sys.exit(1)

    pool_ipv4_relays = ['--pool-relay-ipv4 {} --pool-relay-port {}'.format(relay, relay_port) for relay in relays_ipv4_list]
    pool_dns_relays  = ['--single-host-pool-relay {} --pool-relay-port {}'.format(relay, relay_port) for relay in relays_dns_list]

    final_relays_list = f' '.join(pool_ipv4_relays + pool_dns_relays)

    # if debug:
    #     print('relays:', final_relays_list)

    cmd = [
        "sh",
        "-c",
        f'''cardano-cli stake-pool registration-certificate \
            --cold-verification-key-file {cold_vkey} \
            --vrf-verification-key-file {vrf_vkey} \
            --pool-pledge {pledge_amt} \
            --pool-cost {pool_cost} \
            --pool-margin {margin} \
            --pool-reward-account-verification-key-file {reward_stake_vkey} \
            --metadata-url {metadata_url} \
            --metadata-hash {metadata_hash} \
            {owners_stake_vkeys_args} \
            {final_relays_list} \
            {network} \
            --out-file {output_fname}'''
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
        print(process.stdout.read())
        print("Pool registration certificate creation didn't work")
        sys.exit(1)

    return f'{cwd}/{output_fname}'


def generate_deregistration_cert(cold_vkey, epoch, output_name='pool-deregistration.cert', cwd=None):
    ''' Generates deregistration certificate required for pool retirement

    Runs on an air-gapped offline machine
    '''
    cmd = [
        "sh",
        "-c",
        f'''cardano-cli stake-pool deregistration-certificate \
            --cold-verification-key-file {cold_vkey} \
            --epoch {epoch} \
            --out-file {output_name}'''
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
        print("Was not able to create pool deregistration cert")
        sys.exit(1)

    return f'{cwd}/{output_name}'


def build_tx(tx_in_list, tx_out_list, fee=0, invalid_hereafter=0, withdrawal=False, stake_addr='', certs=[], output_fname='tx.draft', draft=True, cwd=None):
    ''' tx_in_list  - list of input transaction hashes with index. list of strings. string format: "tx_hash#tx_idx"
        tx_out_list - list of output/destination addresses. string format: "address+amount"
        certs - certificates to include and register on blockchain.
                should be list of strings representing full path to certificates.
        output_fname - convention used in many examples:
                       "tx.draft" for a transaction draft
                       "tx.raw" for the actual transaction.

    Runs on an air-gapped offline machine
    '''

    certs_args = ""

    tx_in_args = ' '.join(['--tx-in {}'.format(inhash) for inhash in tx_in_list])

    tx_out_args = ' '.join(['--tx-out {}'.format(outaddr) for outaddr in tx_out_list])

    if isinstance(certs, list):
        if len(certs) > 0:
            certs_args = ' '.join(['--certificate-file {}'.format(cert) for cert in certs])
    else:
        print('"certs" argument should be a list. Received:', certs)
        sys.exit(1)

    if withdrawal and stake_addr:
        withdrawal_args = f'--withdrawal {stake_addr}'
    else:
        withdrawal_args=''

    cmd = [
        "sh",
        "-c",
        f'''cardano-cli transaction build-raw \
            {tx_in_args} \
            {tx_out_args} \
            --invalid-hereafter {invalid_hereafter} \
            --fee {fee} \
            --out-file {output_fname} \
            {certs_args} {withdrawal_args}'''
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
        print(process.stdout.read())
        if draft:
            print("Was not able to build Transaction Draft")
        else:
            print("Was not able to build Raw Transaction")
        sys.exit(1)

    return f'{cwd}/{output_fname}'


def get_tx_fee(tx_file='tx.draft', tx_in_count=1, tx_out_count=1, witnesses=1, byron_witnesses=0, protocol_f_loc='../protocol.json', network='--mainnet', cwd=None):
    ''' Witnesses are the number of keys that will be signing the transaction.
    Examples:
    - at least payment.skey - usual transaction
    - cold.skey stake.skey payment.skey - pool registration
    - cold.skey payment.skey - pool deregisratoin
    - payment.skey stake.skey - stake address registration
    '''

    cmd = [
        "sh",
        "-c",
        f'''cardano-cli transaction calculate-min-fee \
            --tx-body-file {tx_file} \
            --tx-in-count {tx_in_count} \
            --tx-out-count {tx_out_count} \
            --witness-count {witnesses} \
            --byron-witness-count {byron_witnesses} \
            --protocol-params-file {protocol_f_loc} \
            {network}'''
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
        print("Was not able to calculate fees")
        print(process.stdout.read())
        sys.exit(1)

    tx_fee_lovelace_bytes = process.stdout.read()
    tx_fee_lovelace = int(tx_fee_lovelace_bytes.decode("utf-8").split(' ')[0])
    print('Transaction fee:', tx_fee_lovelace)

    return tx_fee_lovelace


def sign_tx(tx_file, signing_keys_list, output_fname='tx.signed', network='--mainnet', cwd=None):
    ''' Witnesses are the number of keys that will be signing the transaction.
    Examples:
    - at least payment.skey - usual transaction
    - cold.skey stake.skey payment.skey - pool registration
    - cold.skey payment.skey - pool deregisratoin
    - payment.skey stake.skey - stake address registration

    Runs on air-gapped offline machine. All signing and cet generation happens on offline machine
    '''

    signing_keys_args = ' '.join(['--signing-key-file {}'.format(skey) for skey in signing_keys_list])

    cmd = [
        "sh",
        "-c",
        f'''cardano-cli transaction sign \
            --tx-body-file {tx_file} \
            {signing_keys_args} \
            {network} \
            --out-file {output_fname}'''
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )
    process.wait()
    process_rc = process.returncode

    proc_stdout_bytes = process.stdout.read()
    if process_rc != 0:
        print(proc_stdout_bytes.decode('utf-8'))
        print('Signing TX did not work.')
        sys.exit(1)
    else:
        print(proc_stdout_bytes.decode('utf-8'))

    return f'{cwd}/{output_fname}'


def submit_tx(signed_tx_f='tx.signed', network='--mainnet', cwd=None):
    '''Submitting signed transaction to blockchain

    requires CARDANO_NODE_SOCKET env variable
    should run on online machine
    '''
    cmd = [
        "sh",
        "-c",
        f"cardano-cli transaction submit --tx-file {signed_tx_f} {network}"
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
        print('Submiting TX did not work.')

    process_out_bytes = process.stdout.read()
    print(process_out_bytes.decode("utf-8"))
