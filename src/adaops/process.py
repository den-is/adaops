import psutil
import json
from pathlib import Path
from pprint import pprint

# https://thispointer.com/python-check-if-a-process-is-running-by-name-and-find-its-process-id-pid/
# https://thispointer.com/python-get-list-of-all-running-processes-and-sort-by-highest-memory-usage/

# determine if process is running
# find cardano-node config
# find cardano-node home dir
# find cardano-node genesis file in cardano-node config
# determine network and magic
# manually add path to config file
# manually indicate path to genesis file
# manually indicate path to protocol file

# add ability to set custom process name
# add ability to set cardano-node home directory
# add ability to set configs files directory
# add ability to set genesis files

CARDANO_NODE_ARGS = {}


def check_cardano_node_proc(proc_name='cardano-node'):
    ''' Checking if cardano-node process exists and extract command line arguments with values
    '''

    for proc in psutil.process_iter():
        try:
            # Check if process name contains the given name string.
            if proc_name.lower() in proc.name().lower():
                key_without_val = None
                for i in proc.cmdline():
                    if i.startswith('--'):
                        key_without_val = i.lstrip('--')
                        CARDANO_NODE_ARGS.setdefault(key_without_val, 'na')
                    elif not i.startswith('--') and key_without_val:
                        CARDANO_NODE_ARGS[key_without_val] = i.strip()

                # print(CARDANO_NODE_ARGS)
                return CARDANO_NODE_ARGS

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            print(f'Was not able to find process "{proc_name}"')

    return None


def get_node_config(file_path='', proc_name='cardano-node'):
    """Looks for config file and returns JSON object.
    """
    config_file = ""

    if file_path:
        if Path(file_path).exists():
            config_file = file_path
        else:
            print(f'Provided config file does not exist: "{file_path}"')

    else:
        process_args = check_cardano_node_proc(proc_name=proc_name)
        if process_args:
            config_file = process_args.get('config', None)
        else:
            print(f'Was not able to find cardano-process and get cofniguration arguments from it. Process "{proc_name}"')

    if not config_file:
        print('Was not able to get config file. Provide config file path or provide correct process name')
        return None, None

    config_raw_path = Path(config_file)
    config_file_dir = config_raw_path.parent

    with open(config_raw_path) as f:
        data = json.load(f)
        return data, str(config_file_dir)


def get_genesis_data(file_path='', phase='shelley', config_file_path='', proc_name='cardano-node'):
    """Returns genesis file data.
    Known issue: cardano-node config should include absolute paths to Genesis files.
    Function won't be able to load relative file paths.
    """

    if phase.lower() not in ['alonzo', 'shelley', 'byron']:
        print(f'Unknow phase "{phase}"')
        return None

    if file_path:
        if Path(file_path).exists():
            genesis_file = file_path
        else:
            print(f'Provided genesis file does not exist: "{file_path}"')

    else:
        config_data = get_node_config(file_path=config_file_path, proc_name=proc_name)[0]
        if not config_data:
            # Exit if no config data returned
            return None

        genesis_key_name = phase.capitalize() + "GenesisFile"
        genesis_file_config = config_data.get(genesis_key_name)
        if Path(genesis_file_config).exists():
            genesis_file = genesis_file_config

    if not genesis_file:
        print('Was not able to get genesis file data')
        return None

    with open(genesis_file) as f:
        data = json.load(f)
        return data
