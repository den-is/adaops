# adaops - Cardano CLI Ops automation

A wrapper ops library mainly around **cardano-cli** and some other helpful funtions to script tedious Cardano workflows in the terminal.

### Requirements
- **cardano-cli** - binary should be discoverable in the `$PATH`
- **v1.27** - is a minimum supported version of cardano-cli (__cardano-node__)
- Python 3.7+

### Example usage
```py
from adaops.lib import get_current_tip
tip = get_current_tip()
print(tip)
# 36019091
```
