import os
import sys
import json
import subprocess
from json import JSONDecodeError

from adaops.lib import check_file_exists

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
