# adaops - Cardano CLI operations automation

Python library to help automate various cardano operations using Python.  
Mainly it is wrapper around **cardano-cli** and bunch of helpful methods.

:warning::hammer_and_wrench: **Under development. Fasten seat belt and wear helmet!** :construction_worker:

- This is work in progress. Depends on my mood, motivation and available free time
- contributions and suggestions are welcome
- provided example scripts are primitive, real scripts should consist of many checks and circuit-breakers
- while this library seems to be primitive
  - it works for me
  - it worked in quite complex scenarios, for various projects and APIs built on top of it
  - library does not cover every command and scenario possible with cardano-cli
  - features were added when some specific scenario needed them
  - features are not re-tested and might be broken, not updated, since I've never returned to them again after initial implementation and usage

## Requirements
- **cardano-cli** - binary should be discoverable in the `$PATH`
- **v10.1.1.0** - is a minimum supported version of cardano-cli
- **CARDANO_NODE_SOCKET_PATH** - Required for online operations. Env variable should be declared and pointing to existing socker of running cardano-node process.
- Python 3.9+

## Installation
Install python any method which is suitable for you.
Short list of options:
- `brew install python` or alternative package manager for your OS, e.g. apt, apk, dnf, yum, ...
- [pyenv](https://github.com/pyenv/pyenv)
- [uv](https://github.com/astral-sh/uv)
- [docker](https://hub.docker.com/_/python)
- [virtualenv](https://virtualenv.pypa.io/en/stable/) + optional [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/stable/)
- built-in [venv](https://docs.python.org/3/library/venv.html) module

Using isolated python environment, rather than system's Python is strongly recommended.

In almost all cases library should have access to an active `CARDANO_NODE_SOCKET_PATH`.
That being said, healthy `cardano-node` should be running on the same machine as `adaops` lib.
Otherwise cardano-node socket should be mounted/forwarded into the environment were code will be executed.

```sh
cd ~

mkdir -p ~/workspace
cd ~/workspace

# Create Python Virtual environment
python3 -m venv venv

# Activate just created Virtual environment
source venv/bin/activate

# Get latest source code
git clone https://github.com/den-is/adaops.git

# Change directory to just cloned directory
cd adaops

# Install library in the venv
pip install -e .
```

## Configuration
Add `.env` file in the root of your project

|ENV                         |Default Value| Description
|----------------------------|-------------|----------------------------------------------------------------------------
|ADAOPS_CARDANO_CLI          |"cardano-cli"|Path to "cardano-cli" either found in $PATH or full path to binary
|CARDANO_NODE_NETWORK_ID     |"mainnet"    |Cardano network to operate on. Possible values: "mainnet", "preprod", "preview"
|CARDANO_NODE_SOCKET_PATH    |             |Required. Path to running cardano-node unix socket
|CARDANO_ERA                 |"conway"     |Required. Supports "legacy", and all other standard era names which can be seen in cardano-cli command groups
|CARDANO_CLI_LEGACY_COMMANDS |"False"      |Use legacy commands under "legacy" commands group. Legacy commands might require legacy era argument `--babbage-era` etc.


## Example usage
```py
from adaops.var import get_current_tip
tip = get_current_tip()
print(tip)
# 36019091
```

You can support my work by sending some ADA:
- `addr1q8qg398j8cyh9k8qf02yhy90t0sdm55q0rhttxfwgve68sgxfhqka2l369tk03nyynll9fqs59dq09njtk7nntkkcasqps24wl`

Provided by [SOUL Cardano Staking pool](https://pooltool.io/pool/3866bed6c94a75ab0290bc86d83467c6557cf2275e8d49b3d727c78c)
