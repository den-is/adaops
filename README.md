# adaops - Cardano CLI Ops automation

A collection of usefull functions to automate different workflows.
Mainly it is wrapper around **cardano-cli** and bunch of other helpful methods.

:warning::hammer_and_wrench: Early development stage. Wear your helmet! :construction_worker:

## Requirements
- **cardano-cli** - binary should be discoverable in the `$PATH`
- **v8.1.2** - is a minimum supported version of cardano-cli (__cardano-node__)
- **CARDANO_NODE_SOCKET_PATH** - Required for online operations. Env variable should be declared and pointing to existing socker of running cardano-node process.
- Python 3.7+

## Installation
At this point of time I strongly recommend to use Python `venv`

```sh
cd ~

# Get latest source code
git clone https://github.com/den-is/adaops.git

# Change directory to just cloned directory
cd adaops

# Create Python Virtual environment
python3 -m venv venv

# Activate just created Virtual environment
source venv/bin/activate

# Install just cloned source code into virtual environment
pip install -e .
```

## Configuration
Add `.env` file in the root of your project

|ENV                     |Default Value| Description                                                       |
|------------------------|-------------|-------------------------------------------------------------------|
|ADAOPS_CARDANO_CLI      |"cardano-cli"|Path to "cardano-cli" either found in $PATH or full path to binary
|CARDANO_NODE_NETWORK_ID |"mainnet"    |Cardano network to operate on. Possible values: "mainnet", "preprod", "preview"
|CARDANO_NODE_SOCKET_PATH|             |
|CARDANO_ERA             |             |Supports "legacy", and all other standard era names which can be seen in cardano-cli command groups
|CARDANO_CLI_LEGACY_COMMANDS |             |Use legacy commands under "legacy" commands group. Legacy commands might require era argument


## Example usage
```py
from adaops.var import get_current_tip
tip = get_current_tip()
print(tip)
# 36019091
```

Provided by [SOUL Cardano Staking pool](https://pooltool.io/pool/3866bed6c94a75ab0290bc86d83467c6557cf2275e8d49b3d727c78c).
