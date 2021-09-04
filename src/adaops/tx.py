import sys
import time
import subprocess

from adaops.var import check_socket_env_var, check_file_exists, get_balances, lovelace2ada

def build_tx(
        tx_in_list,
        tx_out_list,
        fee               = 0,
        invalid_hereafter = 0,
        withdrawal        = False,
        stake_addr        = '',
        certs             = [],
        output_fname      = 'tx.draft',
        draft             = True,
        cwd               = None):

    '''Generates unsigned transaction file. Either draft or raw. Usually should be run on air-gapped machine.

        Is able to generate transactions:
        - Between two or more peers - "simple transaction between receiving addresses"
        - Withdrawing staking rewards from a stake address.
        - Registering certificates on the blockchain.

        tx_in_list  - list of input transaction hashes with index. list of strings. string format: "tx_hash#tx_idx"
        tx_out_list - list of output/destination addresses. string format: "address+amount"
        certs - certificates to include and register on blockchain.
                should be list of strings representing full path to certificates.
        output_fname - convention used in many examples:
                       "tx.draft" for a transaction draft
                       "tx.raw" for the actual transaction.
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

    cmd = f'''cardano-cli transaction build-raw \
        {tx_in_args} \
        {tx_out_args} \
        --invalid-hereafter {invalid_hereafter} \
        --fee {fee} \
        --out-file {output_fname} \
        {certs_args} {withdrawal_args}'''

    process = subprocess.Popen(
        ["sh", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )

    process.wait()
    process_rc = process.returncode
    process_stdout_bytes = process.stdout.read()

    if process_rc != 0:
        print(process_stdout_bytes.decode("utf-8"))
        if draft:
            print("Was not able to build Transaction Draft")
        else:
            print("Was not able to build Raw Transaction")
        print('Failed command was:', cmd)
        sys.exit(1)

    return f'{cwd}/{output_fname}'


def get_tx_fee(
        tx_file         = 'tx.draft',
        tx_in_count     = 1,
        tx_out_count    = 1,
        witnesses       = 1,
        byron_witnesses = 0,
        protocol_f_loc  = '../protocol.json',
        network         = '--mainnet',
        cwd             = None):

    ''' Witnesses are the number of keys that will be signing the transaction.
    Runs on online node.

    Examples:
    - at least payment.skey - usual transaction
    - cold.skey stake.skey payment.skey - pool registration
    - cold.skey payment.skey - pool deregisratoin
    - payment.skey stake.skey - stake address registration
    '''

    check_socket_env_var()

    cmd = f'''cardano-cli transaction calculate-min-fee \
        --tx-body-file {tx_file} \
        --tx-in-count {tx_in_count} \
        --tx-out-count {tx_out_count} \
        --witness-count {witnesses} \
        --byron-witness-count {byron_witnesses} \
        --protocol-params-file {protocol_f_loc} \
        {network}'''

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
        print("Was not able to calculate fees")
        print(decoded_output)
        print('Failed command was:', cmd)
        sys.exit(1)

    tx_fee_lovelace = int(decoded_output.split(' ')[0])

    return tx_fee_lovelace


def sign_tx(tx_file, signing_keys_list, output_fname='tx.signed', network='--mainnet', cwd=None):
    ''' Witnesses are the number of keys that will be signing the transaction.

    Examples:
    - at least "payment.skey" - usual transaction
    - "payment.skey", "stake.skey" - stake address registration
    - "cold.skey", "stake.skey", "payment.skey" - pool registration
    - "cold.skey", "payment.skey" - pool deregisration

    Runs on air-gapped offline machine. All signing and cert generation happens on offline machine
    '''

    signing_keys_args = ' '.join(['--signing-key-file {}'.format(skey) for skey in signing_keys_list])

    cmd = f'''cardano-cli transaction sign \
        --tx-body-file {tx_file} \
        {signing_keys_args} \
        {network} \
        --out-file {output_fname}'''

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
        print(decoded_output)
        print('Signing TX did not work.')
        print('Failed command was:', cmd)
        sys.exit(1)

    return f'{cwd}/{output_fname}'


def submit_tx(signed_tx_f='tx.signed', network='--mainnet', cwd=None):
    '''Submitting signed transaction to blockchain

    requires CARDANO_NODE_SOCKET env variable
    should run on online machine
    '''

    check_socket_env_var()

    cmd = f"cardano-cli transaction submit --tx-file {signed_tx_f} {network}"

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
        print('Submiting TX did not work.')
        print('Failed command was:', cmd)
        print(decoded_output)
        sys.exit(1)

    print(decoded_output.rstrip())


def get_tx_id(tx_file=None, tx_body_file=None):
    '''Return transaction ID using either TX body file, or signed/final TX file

    One of the inputs is required. In case if both are supplied 'tx_file' will take precedence.
    '''

    if not tx_file and not tx_body_file:
        print("Either 'tx_file' or 'tx_body_file' should be provided. None provided")
        sys.exit(1)

    if tx_body_file and not tx_file:
        cmd_tx_arg = '--tx-body-file'
        check_file_exists(tx_file)
        cmd = f"cardano-cli transaction txid {cmd_tx_arg} {tx_body_file}"
    else:
        cmd_tx_arg = '--tx-file'
        check_file_exists(tx_file)
        cmd = f"cardano-cli transaction txid {cmd_tx_arg} {tx_file}"

    process = subprocess.Popen(
        ["sh", "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    process.wait()
    process_rc = process.returncode
    process_stdout_bytes = process.stdout.read()
    decoded_output = process_stdout_bytes.decode("utf-8")

    if process_rc != 0:
        print('Was not able to get transaction ID')
        print('Failed command was:', cmd)
        print(decoded_output)
        sys.exit(1)

    print(decoded_output.strip())
    return(decoded_output.strip())


def wait_for_tx(address, tx_id, timeout=60, network='--mainnet'):
    '''Return transaction ID using either TX body file, or signed/final TX file

    One of the inputs is required. In case if both are supplied 'tx_file' will take precedence.
    '''

    tx_arrived = False
    while not tx_arrived and timeout > 0:

        utxos = get_balances(address=address, network=network)

        for utxo in utxos:
            utxo_hash = utxo['hash'].split('#')[0]
            if utxo_hash == tx_id:
                tx_arrived = True
                lovelace = utxo_hash['balance']
                print(f'Transaction arrived: {tx_id}', '\nBalance {} A ({} L)'.format(lovelace2ada(lovelace), lovelace))
                return

        timeout -= 1
        time.sleep(1)
