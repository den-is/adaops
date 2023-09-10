import logging

from adaops import cardano_cli
from adaops.exceptions import BadCmd
from adaops.var import check_file_exists, cmd_str_cleanup

logger = logging.getLogger(__name__)


def generate_addr_keys(fname="policy", cwd=None):
    """Generates verification and signing crypto keys pair in CWD

    Args:
        fname (str): used as a filename prefix.
            Used to generate two filenames {fname}.skey and {fname}.vkey.
            Defaults to "policy".
        cwd (str): Set working directory. Defaults to None.

    Returns:
        Dictionary:
            {
                "skey": f"{cwd}/{fname}.skey",
                "vkey": f"{cwd}/{fname}.vkey",
            }

    Raises:
        BadCmd: Was not able to generate policy crypto pair
    """

    args = [
        "address",
        "key-gen",
        "--verification-key-file",
        f"{fname}.vkey",
        "--signing-key-file",
        f"{fname}.skey",
    ]

    result = cardano_cli.run(*args, cwd=cwd)

    if result["rc"] != 0:
        logger.error("Was not able to generate policy crypto pair")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to generate policy crypto pair", cmd=result["cmd"])

    return {
        "skey": f"{cwd}/{fname}.skey",
        "vkey": f"{cwd}/{fname}.vkey",
    }


def get_key_hash(key_path):
    """Get hash from Payment Verification key

    Args:
        key_path: Provide full path to payment vkey

    Returns:
        hash - string

    Raises:
        BadCmd: Was not able to get {key_path} key hash
    """
    _key_file = check_file_exists(key_path)

    args = [
        "address",
        "key-hash",
        "--payment-verification-key-file",
        _key_file,
    ]

    result = cardano_cli.run(*args)

    if result["rc"] != 0:
        logger.error(f"Was not able to get {key_path} key hash")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd(f"Was not able to get {key_path} key hash", cmd=result["cmd"])

    key_hash = result["stdout"].strip()
    return key_hash


def get_policy_id(policy_file):
    """Get policy ID

    Args:
        policy_file (str): full path to a policy script file. relative to cwd or full path
        cwd (str): Set working directory. Defaults to None.

    Returns:
        policy_id (str)

    Raises:
        BadCmd: Was not able to generate policy crypto pair
    """

    _policy_file = check_file_exists(policy_file)

    args = [
        "transaction",
        "policyid",
        "--script-file",
        _policy_file,
    ]

    result = cardano_cli.run(*args)

    if result["rc"] != 0:
        logger.error("Was not able to generate policy crypto pair")
        logger.error(result["stderr"])
        logger.error("Failed command was: %s", cmd_str_cleanup(result["cmd"]))
        raise BadCmd("Was not able to generate policy crypto pair", cmd=result["cmd"])

    policy_id = result["stdout"].strip()

    return policy_id


def find_asset_utxo(utxos_json, asset_name, policy_id=None):
    """Return tuple of UTXO(s) that holds specified asset_name

    Works with cardano-node>=1.32.1 and asset names that are hex encoded.
    Balance_json is returned by cardano-cli>1.32.1 and has token names hex encoded.

    Args:
        utxos_json - address balance, JSON that holds all information about address UTXOS with assets
        asset_name - hex string. Asset name you are filtering against
        policy_id - hex string. Policy ID to make search more specific
    """
    utxos = []
    for utxo, assets_map in utxos_json.items():
        if assets_map.get("tokens", False):
            # print(assets_map.get('tokens', False))
            for pol_id, tokens in assets_map.get("tokens").items():
                for token in tokens:
                    if token == asset_name:
                        # if specific policy_id provided check with pol_id under current UTXO
                        if policy_id and policy_id == pol_id:
                            utxos.append(utxo)
                        elif not policy_id:
                            # if no policy_id provided add any UTXO that holds given asset_name
                            utxos.append(utxo)

    return tuple(set(utxos))


def get_assets_str(utxos_json, utxo, asset_name="", policy_id=None, asset_amount=0):
    """Return assets string with counts ready to be inserted in tx_out string 'addr+ada+"get_assets_utxo_str()"'

    utxos_json - JSON/Dictionary represeneting complete balance, all UTXOs, of that address
    utxo - specific UTXO that holds assets
    asset_name - asset/token name whos count is being manipulated
    policy_id - policy_id for more precise filtering, immediately drops items that are not under specific policy_id
    asset_amount - amount of assets to deduct from original amount. for sending or burning.

    ### TODO: Try to generate assets strings right away from passed "utxos_json".
    #         Right now method works only with one UTXO at the time.
    ### TODO: Maybe allow allow list of specific UTXOs too.
    ### TODO: Working with whole 'utxos_json' at once might help with situation when several UTXOs under the same address
    #         hold the very same "policy_id.token_name". In that case you need to aggregate token amounts into one number.
    ### TODO: What if you are sending more then one token, but different tokens.
    #         And each token has different amounts to send or burn?
    #         Each token should have own asset_amount to deduct from the base assets balance.
    ### TODO: What if asset count drops to 0 - not to include that asset in output?
    #         I.e. situation when sending all tokens to someone else or burning.
    """

    utxo_balance = utxos_json[utxo]
    utxo_tokens = utxo_balance.get("tokens", None)

    # return None if UTXO has no tokens balance
    if not utxo_tokens:
        return

    tokens_str_lst = []
    for pol_id, tokens in utxo_tokens.items():
        if policy_id and not pol_id == policy_id:
            continue
        for token_name, count in tokens.items():
            if token_name == asset_name:
                count -= asset_amount
                if count < 0:
                    count = 0
            str_repr = f"{count} {pol_id}.{token_name}"
            tokens_str_lst.append(str_repr)

    all_assets_str = " + ".join(tokens_str_lst)

    return all_assets_str
