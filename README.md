# adaops - Cardano CLI Ops automation

A collection of usefull functions to automate different workflows.
Mainly it is wrapper around **cardano-cli** and bunch of other helpful methods.

### Requirements
- **cardano-cli** - binary should be discoverable in the `$PATH`
- **v1.27** - is a minimum supported version of cardano-cli (__cardano-node__)
- **CARDANO_NODE_SOCKET_PATH** - Required for online operations. Env variable should be declared and pointing to existing socker of running cardano-node process.
- Python 3.7+

### Example usage
```py
from adaops.lib import get_current_tip
tip = get_current_tip()
print(tip)
# 36019091
```

Provided by [SOUL Cardano Staking pool](https://pooltool.io/pool/3866bed6c94a75ab0290bc86d83467c6557cf2275e8d49b3d727c78c).
