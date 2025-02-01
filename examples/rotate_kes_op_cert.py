import json

from adaops.certs import generate_node_cert
from adaops.cold import generate_node_kes_keys
from adaops.var import current_kes_period, get_current_tip

CWD = "/home/user/pool"

GENESIS_F = f"{CWD}/mainnet-shelley-genesis.json"

genesis_data = None
with open(GENESIS_F) as json_file:
    genesis_data = json.load(json_file)


current_tip = get_current_tip()

current_kes_period = current_kes_period(current_tip, genesis_data)

print("Current tip's slot of the network:", current_tip)
print("Current KES period:", current_kes_period)

generate_node_kes_keys(cwd=CWD)

node_cert = generate_node_cert(
    kes_vkey=f"{CWD}/cold_keys/kes.vkey",
    cold_skey=f"{CWD}/cold_keys/cold.skey",
    cold_counter=f"{CWD}/cold_keys/cold.counter",
    kes_period=current_kes_period,
    output_name="cold_keys/node.cert",
    cwd=CWD,
)
