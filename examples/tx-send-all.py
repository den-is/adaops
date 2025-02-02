# Send all Ada from addr1 to addr2
# UTXOs have ADA only
#
# python 3.13.1
# cardano-node 10.1.4
# cardano-cli 10.1.1.0
# adaops v2.3.2
# export CARDANO_ERA=conway
# export CARDANO_NODE_NETWORK_ID=1
# no "legacy" group commands

import logging
from pathlib import Path

from adaops.tx import build_tx, get_tx_fee, get_tx_id, sign_tx, submit_tx, wait_for_tx
from adaops.var import (
    get_balances,
    get_current_tip,
    get_total_balance,
    l2a,
)


### Basic logging setup ---------------------------------------------------------
def logging_setup(log_file):
    log_file_name = log_file
    log_date_fmt = "%Y-%m-%d %H:%M:%S"
    log_msg_fmt = "%(asctime)s [%(levelname)s][%(name)s:L%(lineno)d][fn:%(funcName)s] %(message)s"

    # log to file
    logging.basicConfig(
        filename=log_file_name,
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


### Main -----------------------------------------------------------------------
def transaction(
    src_addr,
    dst_addr,
    recepient_name,
    signing_keys,
    output_dir,
    output_name_prefix,
    timeout=1200,
    invalid_hereafter=1200,
):

    # get total balance to send to dst_addr
    total_amount = get_total_balance(src_addr)
    if not total_amount:
        logging.error("Make sure src address has balance - got 0 balance. Exiting.")
        exit(1)

    logging.info("Sending %f (%d L) to %s", l2a(total_amount), total_amount, recepient_name)
    logging.info(f"Src_addr: {src_addr}")
    logging.info(f"Dst_addr: {dst_addr}")

    balance_hashes = get_balances(src_addr)

    # here you can replace input_list with the list of all src hashes
    # usefull during migration and transfering all funds from given account by listing all of its nonempty utxos
    # but don't forget to get Total Balance
    input_list = list(balance_hashes.keys())
    if not input_list:
        logging.error("Make sure src address has balance/UTXOs. Got empty list. Exiting")
        exit(1)
    logging.info("Source UTXOs count %d", len(input_list))
    logging.info("Source UTXOs list: %s", ",".join(input_list))

    # below there is `final_output_list` variable that is the same list of dst addresses,
    # but with final/real amounts
    # during migration only DST addr is needed, i.e. no need to return change to SRC address
    draft_output_list = [f"{dst_addr}+{total_amount}"]

    # since conway you need to provide not null values as possible
    # fee can't be 0 - 200_000 or more should work
    # invalid_hereafter slot can be set too
    # amount to send in tx_out_list is not precisely but is known to - in our case it is "{dst_addr}+{total_amount}"

    current_tip = get_current_tip()

    tx_draft = build_tx(
        tx_in_list=input_list,
        tx_out_list=draft_output_list,
        fee=200_000,
        invalid_hereafter=current_tip + invalid_hereafter,
        cwd=output_dir,
        output_fname=f"{output_name_prefix}.draft",
        draft=True,
    )

    tx_fee_lovelace = get_tx_fee(
        tx_file=tx_draft,
        tx_in_count=len(input_list),
        tx_out_count=len(draft_output_list),
        witnesses=len(signing_keys),
        protocol_fpath=PROTOCOL_FILE,
        cwd=output_dir,
    )

    logging.info("TX fee: %f A (%d L)", l2a(tx_fee_lovelace), tx_fee_lovelace)

    # destination gets all - tx fee
    dst_amount = total_amount - tx_fee_lovelace
    # owner gets 0. no need to add it to final_output_list or draft_output_list
    # src_remainder = 0

    logging.info(
        "Net TX amount after fee: %f A (%d L)",
        l2a(dst_amount),
        dst_amount,
    )

    current_tip = get_current_tip()

    final_output_list = [f"{dst_addr}+{dst_amount}"]

    tx_raw = build_tx(
        tx_in_list=input_list,
        tx_out_list=final_output_list,
        fee=tx_fee_lovelace,
        invalid_hereafter=current_tip + invalid_hereafter,
        cwd=output_dir,
        output_fname=f"{output_name_prefix}.raw",
        draft=False,
    )

    tx_signed = sign_tx(
        tx_file=tx_raw,
        signing_keys_list=signing_keys,
        cwd=output_dir,
        output_fname=f"{output_name_prefix}.signed",
    )

    tx_id = get_tx_id(tx_file=tx_signed)

    submit_success = submit_tx(signed_tx_f=tx_signed, cwd=output_dir)

    if submit_success:
        if timeout < invalid_hereafter:
            timeout = invalid_hereafter

        # TODO: Large TODO section and brainstorming
        # wait_for_tx should be waiting as long as there is invalid_hereafter value
        # If --invalid-[hereafter|before] is not set you should not wait for
        # expiration just report how long it took for transaction to appear
        #
        # during migration you have to check dst_addr for new transaction instead of src_addr
        wait_for_tx(dst_addr, tx_id, timeout=timeout)
        # get status from wait_for_tx, if success or expired


if __name__ == "__main__":
    PROTOCOL_FILE = "/root/workspace/protocol.json"
    OUTPUT_DIR = Path("/root/workspace/scripts/output/tx-send-all")
    try:
        OUTPUT_DIR.mkdir(parents=True)
    except FileExistsError as e:
        logging.error(f"Make sure output dir does not exist.\n{e}")
        exit(1)

    logging_setup(OUTPUT_DIR / "tx.log")

    # src bech32 address
    addr1 = "addr_test1a0123456789"
    addr1_sign_key = "/home/user/workspace/addr1/payment.skey"
    # dst bech32 address
    addr2 = "addr_test1a9876543210"

    transaction(
        src_addr=addr1,
        dst_addr=addr2,
        recepient_name="Main wallet",
        signing_keys=[addr1_sign_key],
        output_dir=OUTPUT_DIR,
        output_name_prefix="tx",
        timeout=1200,
        invalid_hereafter=1200,
    )

    exit(0)
