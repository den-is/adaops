import logging
import subprocess
import sys

from adaops.var import cmd_str_cleanup

logger = logging.getLogger(__name__)


def generate_node_cert(
    kes_vkey, cold_skey, cold_counter, kes_period, output_name="node.cert", cwd=None
):
    """Generate Node Operational certificate
    requires renewal as soon as KES key pair is renewed

    kes_vkey - path to kes.vkey
    cold_skey - path to cold.skey
    cold_counter - path to cold.counter
    kes_period - integer, current KES period
    """

    cmd = f"""cardano-cli node issue-op-cert \
        --kes-verification-key-file {kes_vkey} \
        --cold-signing-key-file {cold_skey} \
        --operational-certificate-issue-counter {cold_counter} \
        --kes-period {kes_period} \
        --out-file {output_name}"""

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
        logger.error("Was not able to generate node cert")
        logger.error(decoded_output)
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    return f"{cwd}/{output_name}"


def generate_stake_reg_cert(output_name="stake.cert", stake_vkey="stake.vkey", cwd=None):
    """Generate stake address registration certificate

    Runs on an air-gapped offline machine
    """

    cmd = f"""cardano-cli stake-address registration-certificate \
        --stake-verification-key-file {stake_vkey} \
        --out-file {output_name}"""

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
        logger.error("Was not able to create stake registration cert")
        logger.error(decoded_output)
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    return f"{cwd}/{output_name}"


def generate_delegation_cert(output_name, owner_stake_vkey, cold_vkey, cwd=None):
    """Generations stake delegation certificate for the owner

    Runs on an air-gapped offline machine
    """

    cmd = f"""cardano-cli stake-address delegation-certificate \
        --stake-verification-key-file {owner_stake_vkey} \
        --cold-verification-key-file {cold_vkey} \
        --out-file {output_name}"""

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
        logger.error("Owner's Delegation cert creation didn't work")
        logger.error(decoded_output)
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    return f"{cwd}/{output_name}"


def generate_pool_reg_cert(
    cold_vkey,
    vrf_vkey,
    pledge_amt,
    pool_cost,
    margin,
    reward_stake_vkey,
    owners_stake_vkeys_list,
    metadata_hash,
    metadata_url,
    relay_port,
    relays_ipv4_list=None,
    relays_dns_list=None,
    network="--mainnet",
    cwd=None,
    output_fname="pool-registration.cert",
):

    """There might be multiple pool-owner-stake-verification keys
    owners_vkeys - list of string paths to Stake VKEYs.
                   Generate into appropriate argument internaly.

    All relays should be running on the same port.

    relays_ipv4_list - list of string in format 'pool_ipv4:port'

    Runs on an air-gapped offline machine
    """

    if relays_ipv4_list is None:
        relays_ipv4_list = []

    if relays_dns_list is None:
        relays_dns_list = []

    if len(metadata_url) > 64:
        logger.error("Metadata URL is longer than 64 characters: %s", metadata_url)

    if not isinstance(owners_stake_vkeys_list, list):
        logger.error(
            "owners_stake_vkeys - list of strings with full path to owner stake verification keys"
        )
        sys.exit(1)

    owners_stake_vkeys_args = " ".join(
        [
            "--pool-owner-stake-verification-key-file {}".format(vkey_path)
            for vkey_path in owners_stake_vkeys_list
        ]
    )

    if not relays_dns_list and not relays_ipv4_list:
        logger.error("Neither relays_dns_list or relays_ipv4_list supplied")
        sys.exit(1)

    pool_ipv4_relays = [
        "--pool-relay-ipv4 {} --pool-relay-port {}".format(relay, relay_port)
        for relay in relays_ipv4_list
    ]
    pool_dns_relays = [
        "--single-host-pool-relay {} --pool-relay-port {}".format(relay, relay_port)
        for relay in relays_dns_list
    ]

    final_relays_list = " ".join(pool_ipv4_relays + pool_dns_relays)

    # if debug:
    #     print('relays:', final_relays_list)

    cmd = f"""cardano-cli stake-pool registration-certificate \
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
        --out-file {output_fname}"""

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
        logger.error("Pool registration certificate creation didn't work")
        logger.error(decoded_output)
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    return f"{cwd}/{output_fname}"


def generate_deregistration_cert(
    cold_vkey, epoch, output_name="pool-deregistration.cert", cwd=None
):
    """Generates a pool deregistration certificate required for the pool retirement

    Runs on an air-gapped offline machine
    """

    cmd = f"""cardano-cli stake-pool deregistration-certificate \
        --cold-verification-key-file {cold_vkey} \
        --epoch {epoch} \
        --out-file {output_name}"""

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
        logger.error("Was not able to create pool deregistration cert")
        logger.error(decoded_output)
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    return f"{cwd}/{output_name}"


def generate_stake_dereg_cert(
    stake_vkey,
    output_name="stake-deregistration.cert",
    cwd=None,
):
    """Generates a stake delegation deregistration certificate

    Runs on an air-gapped offline machine
    """

    cmd = f"""cardano-cli stake-address deregistration-certificate \
        --stake-verification-key-file {stake_vkey} \
        --out-file {output_name}"""

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
        logger.error("Was not able to create stake address deregistration cert")
        logger.error(decoded_output)
        logger.error("Failed command was: %s", cmd_str_cleanup(cmd))
        sys.exit(1)

    return f"{cwd}/{output_name}"
