# Basic ADA transaction from one address to another
# Source address UTXOs have ADA only
# ability to set if sender pays the fee or the receiver
# i.e. receiver gets full amount or amount with deducted transaction fee
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
from adaops.var import a2l, get_balances, get_current_tip, get_utxo_with_enough_balance, l2a


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


def transaction(
    src_addr,
    dst_addr,
    amount,
    recepient_name,
    signing_keys,
    output_dir,
    output_name_prefix,
    src_utxo=None,
    receiver_pays=True,
    timeout=1200,
    invalid_hereafter=1200,
):
    logging.info("Sending %f (%d L) to %s", l2a(amount), amount, recepient_name)
    logging.info(f"Src_addr: {src_addr}")
    logging.info(f"Dst_addr: {dst_addr}")

    balance_hashes = get_balances(src_addr)

    if not src_utxo:
        utxo_hash = get_utxo_with_enough_balance(balance_hashes, amount)
    else:
        # Use user provided known utxo hash. makes sure it is in "utxo_hash#idx" format
        if src_utxo not in list(balance_hashes.keys()):
            logging.error(
                f"Provided UTXO is not found under provided address {src_addr}, utxo {src_utxo}"
            )
            utxo_hash = None

        elif balance_hashes[src_utxo]["lovelace"] < amount:
            logging.error(
                "Provided UTXO has not enough funds to complete transaction %s, utxo %s, balance %s",
                dst_addr,
                src_utxo,
                balance_hashes[src_utxo]["lovelace"],
            )
            utxo_hash = None
        else:
            utxo_hash = src_utxo

    if not utxo_hash:
        logging.error("Cannot procceed without UTXO hash with enough balance")
        logging.error(
            "Pass either address or a specific utxo with enough balance to pay transaction fees"
        )
        exit(1)

    utxo_balance = balance_hashes[utxo_hash]["lovelace"]
    logging.info("Selected IN-utxo#id and its balance: %s, %s", utxo_hash, utxo_balance)

    # here you can replace input_list with the list of all src hashes
    # usefull during migration and transfering all funds from given account by listing all of its nonempty utxos
    # but don't forget to get Total Balance
    input_list = [utxo_hash]
    # below there is `final_output_list` variable that is the same list of dst addresses,
    # but with final/real amounts
    # during migration only DST addr is needed
    draft_output_list = [f"{src_addr}+{utxo_balance - amount}", f"{dst_addr}+{amount}"]

    # since conway you need to provide not null values as possible
    # fee can't be 0 - 200_000 or more should work
    # invalid_hereafter slot can be set too
    # amount to send in tx_out_list is not precice but can be approximate
    #   in our case it is "{src_addr}+{utxo_balance - amount}", f"{dst_addr}+{amount}"

    current_tip = int(get_current_tip())

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

    if receiver_pays:
        # receiver pays the fee = receives "amount - fee"
        dst_amount = amount - tx_fee_lovelace
    else:
        # used when Sender/Source pays the transaction fee and receiver gets
        #   full amount without deduction
        # also used during migration. Since Source initiates transaction
        # - Source Sends all funds to dst and has to pay transaction fee
        #   nothing should be left at source
        dst_amount = amount

    # src address = balance - dst_amount - tx_fee
    src_remainder = utxo_balance - dst_amount - tx_fee_lovelace

    logging.info(
        "Net TX amount after fee: %f A (%d L)",
        l2a(dst_amount),
        dst_amount,
    )

    current_tip = int(get_current_tip())

    final_output_list = [f"{src_addr}+{src_remainder}", f"{dst_addr}+{dst_amount}"]

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
        wait_for_tx(src_addr, tx_id, timeout=timeout)
        # get status from wait_for_tx, if success or expired


if __name__ == "__main__":
    PROTOCOL_FILE = "/home/user/workspace/protocol.json"
    OUTPUT_DIR = Path("/home/user/workspace/scripts/output/tx-basic")
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
    ADA_TO_SEND = 15
    LOVELACES_TO_SEND = a2l(ADA_TO_SEND)  # library operates on Lovelaces

    transaction(
        src_addr=addr1,
        dst_addr=addr2,
        amount=LOVELACES_TO_SEND,
        recepient_name="Secondary wallet",
        signing_keys=[addr1_sign_key],
        output_dir=OUTPUT_DIR,
        output_name_prefix="tx",
        receiver_pays=False,
        timeout=1200,
        invalid_hereafter=1200,
    )
