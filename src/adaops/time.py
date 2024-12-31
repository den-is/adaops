import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from icalendar import Calendar, Event

from adaops.var import get_current_tip

logger = logging.getLogger(__name__)


def calculate_current_epoch(genesis_data):
    """Calculates current epoch based on system time and genesis file.

    Offline method calculates values based on genesis file and system time.
    genesis_data - JSON object containing Shelley genesis data.

    Quick reference values:
        2017-09-23T21:44:51Z - cardano mainnet start date
        2019-07-24T20:20:16Z - cardano testnet start date
        432000 - epoch length/duration, in seconds. mainnet and testnet

    Returns:
      epoch - int

    Raises:
        KeyError: If genesis_data is missing "systemStart" or "epochLength" keys.
    """
    try:
        cardano_start_str = genesis_data["systemStart"]
        epoch_len = int(genesis_data["epochLength"])
    except KeyError as err:
        logger.error(
            'Not able to find "systemStart" or "epochLength" in genesis data. '
            "Make sure you have passed correct genesis file."
        )
        raise KeyError('Genesis file is missing "systemStart" or "epochLength" keys') from err

    now = datetime.now(timezone.utc)
    cardano_start_dt = datetime.strptime(cardano_start_str, "%Y-%m-%dT%H:%M:%SZ")
    time_since_start = now - cardano_start_dt
    time_since_start_sec = time_since_start.total_seconds()

    return int(time_since_start_sec / epoch_len)


def time_in_epoch(genesis_data):
    """Calculates time in current epoch in seconds.

    Offline method calculates values based on genesis file and system time.
    genesis_data - JSON object containing Shelley genesis data.

    Quick reference values:
        2017-09-23T21:44:51Z - cardano mainnet start date
        2019-07-24T20:20:16Z - cardano testnet start date
        432000 - epoch length/duration, in seconds. mainnet and testnet

    Examples:
        To calculate full days in epoch, i.e. to determine first or last days:
            int(time_in_epoch() / 86400 ) % 5

    Returns:
        seconds - float, rounded to 1 digit after period

    Raises:
        KeyError: If genesis_data is missing "systemStart" or "epochLength" keys.
    """

    try:
        cardano_start_str = genesis_data["systemStart"]
        epoch_len = int(genesis_data["epochLength"])
    except KeyError as err:
        logger.error(
            'Not able to find "systemStart" or "epochLength" in genesis data. '
            "Make sure you have passed correct genesis file."
        )
        raise KeyError('Genesis file is missing "systemStart" or "epochLength" keys') from err

    now = datetime.now(timezone.utc)
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

    Returns:
        seconds - float, rounded to 1 digit after period.

    Raises:
        KeyError: If genesis_data is missing "systemStart" or "epochLength" keys.
    """
    try:
        cardano_start_str = genesis_data["systemStart"]
        epoch_len = int(genesis_data["epochLength"])
    except KeyError as err:
        logger.error(
            'Not able to find "systemStart" or "epochLength" in genesis data. '
            "Make sure you have passed correct genesis file."
        )
        raise KeyError('Genesis file is missing "systemStart" or "epochLength" keys') from err

    now = datetime.now(timezone.utc)
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

    Returns:
        datetime object - epoch date in UTC timezone

    Raises:
        KeyError: If genesis_data is missing "systemStart" or "epochLength" keys.
    """
    try:
        cardano_start_str = genesis_data["systemStart"]
        epoch_len = int(genesis_data["epochLength"])
    except KeyError as err:
        logger.error(
            'Not able to find "systemStart" or "epochLength" in genesis data. '
            "Make sure you have passed correct genesis file."
        )
        raise KeyError('Genesis file is missing "systemStart" or "epochLength" keys') from err

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
    current_slot = get_current_tip()
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


def generate_epochs_calendar(
    start_epoch,
    end_epoch,
    genesis_data,
    RFC5545_prodid,
    dst="cardano_calendar.ics",
    RFC5545_version="2.0",
):
    """Generates calendar file, with list of new cardano epoch events.
    Dates are in UTC timezone.

    Returns Path object of a destination file.

    Args:
        start_epoch - int. First epoch in range to start with. Example 390
        end_epoch   - int. Last epoch to end range with. Excluded from range. Example 1000
        dst         - str. Resulting file destination "cardano_calendar.ics"
        genesis_data - map. Python map representing Shelley genesis data.
                       Usually loaded from genesis JSON file
        RFC5545_prodid - Calendar prodid. More info bellow.
        RFC5545_version - Calendar version. More info bellow. Keep it as "2.0".
                          Don't change if not asked by RFC or icalendar lib.

    Requires calendar PRODID and Version string values as by RFC5545 https://datatracker.ietf.org/doc/html/rfc5545:
        RFC5545_prodid = "-//My calendar//example.com//
        RFC5545_version = "2.0" - Don't change it.

    Requires shelley genesis config:
        with open("/opt/cardano/configs/shelley-genesis.json") as shelley_file:
            genesis_data = json.load(shelley_file)
    """
    cal = Calendar()
    cal.add("prodid", RFC5545_prodid)
    cal.add("version", RFC5545_version)

    for epoch in range(start_epoch, end_epoch):
        event = Event()
        event.add("summary", f"{epoch} - cardano epoch")
        event.add("dtstart", calculate_epoch_date(epoch, genesis_data))
        cal.add_component(event)

    dst_file = Path(dst)
    dst_file.write_bytes(cal.to_ical())

    return dst_file
