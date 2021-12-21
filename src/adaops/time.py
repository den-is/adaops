import logging
import sys
import time
from datetime import datetime, timedelta

from adaops.var import get_current_tip

logger = logging.getLogger(__name__)


def calculate_current_epoch(genesis_data):
    """Calculates current epoch based on system time and genesis file.

    Offline method calculates values based on genesis file and system time.
    genesis_data - JSON object containing Shelley genesis data.

    quick reference values:
    2017-09-23T21:44:51Z - cardano mainnet start date
    2019-07-24T20:20:16Z - cardano testnet start date
    432000 - epoch length/duration, in seconds. mainnet and testnet

    returns epoch - int
    """
    cardano_start_str = genesis_data.get("systemStart")
    epoch_len = int(genesis_data.get("epochLength", 0))

    if not cardano_start_str or not epoch_len:
        logger.error(
            'Not able to find "systemStart" or "epochLength" in genesis data. '
            "Make sure you have passed correct genesis file."
        )

        sys.exit(1)

    now = datetime.utcnow()
    cardano_start_dt = datetime.strptime(cardano_start_str, "%Y-%m-%dT%H:%M:%SZ")
    time_since_start = now - cardano_start_dt
    time_since_start_sec = time_since_start.total_seconds()

    return int(time_since_start_sec / epoch_len)


def time_in_epoch(genesis_data):
    """Calculates time in current epoch in seconds.

    Offline method calculates values based on genesis file and system time.
    genesis_data - JSON object containing Shelley genesis data.

    quick reference values:
    2017-09-23T21:44:51Z - cardano mainnet start date
    2019-07-24T20:20:16Z - cardano testnet start date
    432000 - epoch length/duration, in seconds. mainnet and testnet

    Examples:
        To calculate full days in epoch, i.e. to determine first or last days:
            int(time_in_epoch() / 86400 ) % 5

    returns:
    seconds - float, rounded to 1 digit after period
    """
    cardano_start_str = genesis_data.get("systemStart")
    epoch_len = int(genesis_data.get("epochLength", 0))

    if not cardano_start_str or not epoch_len:
        logger.error(
            'Not able to find "systemStart" or "epochLength" in genesis data. '
            "Make sure you have passed correct genesis file."
        )
        sys.exit(1)

    now = datetime.utcnow()
    cardano_start_dt = datetime.strptime(cardano_start_str, "%Y-%m-%dT%H:%M:%SZ")
    time_since_start = now - cardano_start_dt
    time_since_start_sec = time_since_start.total_seconds()
    current_epoch = int(time_since_start_sec / epoch_len)
    total_epoch_seconds = current_epoch * epoch_len

    return round(time_since_start_sec - total_epoch_seconds, 1)


def time_until_next_epoch(genesis_data):
    """Calculates time until next epoch in seconds

    Offline method calculates values based on genesis file and system time.
    genesis_data - JSON object containing Shelley genesis data.

    returns:
    seconds - float, rounded to 1 digit after period.
    """
    cardano_start_str = genesis_data.get("systemStart")
    epoch_len = int(genesis_data.get("epochLength", 0))

    if not cardano_start_str or not epoch_len:
        logger.error(
            'Not able to find "systemStart" or "epochLength" in genesis data. '
            "Make sure you have passed correct genesis file."
        )
        sys.exit(1)

    now = datetime.utcnow()
    cardano_start_dt = datetime.strptime(cardano_start_str, "%Y-%m-%dT%H:%M:%SZ")
    time_since_start = now - cardano_start_dt
    time_since_start_sec = time_since_start.total_seconds()
    current_epoch = int(time_since_start_sec / epoch_len)

    next_epoch_in = epoch_len - (time_since_start_sec - current_epoch * epoch_len)

    return round(next_epoch_in, 1)


def calculate_epoch_date(epoch, genesis_data):
    """Returns datetime object for specific epoch. UTC

    Offline method calculates values based on genesis file and system time.
    genesis_data - JSON object containing Shelley genesis data.
    epoch - int

    returns:
    datetime object
    """
    cardano_start_str = genesis_data.get("systemStart")
    epoch_len = int(genesis_data.get("epochLength", 0))

    if not cardano_start_str or not epoch_len:
        logger.error(
            'Not able to find "systemStart" or "epochLength" in genesis data. '
            "Make sure you have passed correct genesis file."
        )
        sys.exit(1)

    cardano_start_dt = datetime.strptime(cardano_start_str, "%Y-%m-%dT%H:%M:%SZ")

    total_epoch_seconds = epoch * epoch_len

    epoch_date = cardano_start_dt + timedelta(seconds=total_epoch_seconds)

    return epoch_date


def kes_expiration_sec(remaining_kes_periods, genesis_data, network="--mainnet"):
    """Returns seconds until current KES keys expiration

    remaining_periods - Int. returned by cardano-node metrics.
                        Or if pool's start KES period is known:
                        genesis['maxKESEvolutions'] - (current_kes_period - start_kes_period)
    genesis_data - json object representing Shelley genesis data

    Returns:
        {
            'seconds_remaining': remaining_seconds, int
            'expiration_timestamp': kes_ekpiration_timestamp, int
        }
    """
    current_slot = get_current_tip(network=network)
    slot_length = genesis_data.get("slotLength")  # mainnet = 1
    slots_per_kes = genesis_data.get("slotsPerKESPeriod")  # mainnet = 129600

    now_sec_since_epoch = int(time.time())

    remaining_kes_seconds_total = slot_length * slots_per_kes * remaining_kes_periods
    seconds_current_period = slot_length * (current_slot % slots_per_kes)

    remaining_seconds = remaining_kes_seconds_total - seconds_current_period
    kes_ekpiration_timestamp = now_sec_since_epoch + remaining_seconds
    # or datetime.utcnow+timedelta(seconds=(remaining_kes_seconds_total - seconds_current_period))

    return {
        "seconds_remaining": remaining_seconds,
        "expiration_timestamp": kes_ekpiration_timestamp,
    }
