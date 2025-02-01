# This specific example script supports only simple address with ADA only
#   it does not support address with other assets (NFT,...)
#   otherwise you need to add logic to return all assets (ADA, NFT,...) as change
# Tested with cardano-cli 10.1.1.0, cardano-node 10.1.3, python 3.12
# This is a basic example which works as is, more professional setup would require comprehensive test suite
#
# Run:
#   python governance_vote_hardfork_plomin.py
#
import logging

from adaops.governance import governance_action_view_vote_f, governance_action_vote_with_pool
from adaops.tx import build_tx, get_tx_fee, get_tx_id, sign_tx, submit_tx
from adaops.var import get_balances, get_current_tip, get_utxo_with_enough_balance, l2a

# https://gov.tools/connected/governance_actions/0b19476e40bbbb5e1e8ce153523762e2b6859e7ecacbaf06eae0ee6a447e79b9#0
# https://adastat.net/governances/0b19476e40bbbb5e1e8ce153523762e2b6859e7ecacbaf06eae0ee6a447e79b900
ACTION_UTXO_ID = "0b19476e40bbbb5e1e8ce153523762e2b6859e7ecacbaf06eae0ee6a447e79b9"
ACTION_UTXO_IDX = "0"

VOTE = "yes"  # <--- your decision. one of: "yes", "no", "abstain"

CWD = ""
POOL_VKEY = "cold.vkey"
PAYMENT_ADDR = "addr1..."  # get address value from payment.addr file or any other
SIGNING_KEYS = ["cold.skey", "payment.skey"]

PROTOCOL_FILE = "protocol.json"
invalid_hereafter = 1200
output_fname_prefix = "vote-hardfork-plomin"

## Setup basic logging ---------------------------------------------------------
log_date_fmt = "%Y-%m-%d %H:%M:%S"
log_msg_fmt = "%(asctime)s [%(levelname)s][%(name)s:L%(lineno)d][fn:%(funcName)s] %(message)s"

# log to file
logging.basicConfig(
    filename=f"{output_fname_prefix}.log",
    filemode="a",
    encoding="utf-8",
    level=logging.DEBUG,
    format=log_msg_fmt,
    datefmt=log_date_fmt,
)

# log to console too
console_log = logging.StreamHandler()
console_log.setLevel(logging.DEBUG)
console_log.setFormatter(logging.Formatter(fmt=log_msg_fmt, datefmt=log_date_fmt))
logging.getLogger("").addHandler(console_log)

## Create a Vote file ----------------------------------------------------------
vote_file = governance_action_vote_with_pool(
    governance_action_tx_id=ACTION_UTXO_ID,
    governance_action_index=ACTION_UTXO_IDX,
    decision=VOTE,
    cold_verification_key_file=POOL_VKEY,
    output_name=f"{output_fname_prefix}.json",
    cwd=CWD,
)

logging.info("-" * 80)
logging.info(f"Vote file: {vote_file}")
logging.info(governance_action_view_vote_f(vote_file))

## Build a transaction to submit the vote --------------------------------------

balance_hashes = get_balances(PAYMENT_ADDR)
min_balance_lovelaces = 10_000_000  # minimum 10A (just. a couple of ADA will do too)
utxo_hash = get_utxo_with_enough_balance(balance_hashes, min_balance_lovelaces)
utxo_balance = balance_hashes[utxo_hash]["lovelace"]

current_tip = int(get_current_tip())

tx_draft = build_tx(
    tx_in_list=[utxo_hash],
    tx_out_list=[f"{PAYMENT_ADDR}+{utxo_balance}"],
    fee=300000,
    invalid_hereafter=current_tip + invalid_hereafter,
    extra_args=f"--vote-file {vote_file}",
    output_fname=f"{output_fname_prefix}.draft.tx",
    cwd=CWD,
    draft=True,
)

tx_fee_lovelace = get_tx_fee(
    tx_file=tx_draft,
    tx_in_count=1,
    tx_out_count=1,
    witnesses=len(SIGNING_KEYS),
    protocol_fpath=PROTOCOL_FILE,
    cwd=CWD,
)

logging.info("-" * 80)
logging.info(f"Fee: {tx_fee_lovelace} ({l2a(tx_fee_lovelace)}A)")
change = utxo_balance - tx_fee_lovelace
logging.info(f"Change: {change} ({l2a(change)}A)")

tx_raw = build_tx(
    tx_in_list=[utxo_hash],
    tx_out_list=[f"{PAYMENT_ADDR}+{change}"],
    fee=tx_fee_lovelace,
    invalid_hereafter=current_tip + invalid_hereafter,
    extra_args=f"--vote-file {vote_file}",
    output_fname=f"{output_fname_prefix}.raw.tx",
    cwd=CWD,
    draft=False,
)

tx_signed = sign_tx(
    tx_file=tx_raw,
    signing_keys_list=SIGNING_KEYS,
    cwd=CWD,
    output_fname=f"{output_fname_prefix}.signed.tx",
)

tx_id = get_tx_id(tx_file=tx_signed)

logging.info(f"TX ID: {tx_id}")

logging.info("-" * 80)

submit_success = False
try:
    submit_success = submit_tx(signed_tx_f=tx_signed, cwd=CWD)
except Exception as e:
    logging.error(e)
logging.warning(f"Submitted: {submit_success}")
