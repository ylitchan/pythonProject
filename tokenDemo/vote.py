import requests
from jsonpath_ng import parse

response = requests.get("https://cloud-prod.equilibria.fi/api/chain-info")
marketInfo = response.json()
symbols = {}
for m in parse('$..marketInfo').find(marketInfo):
    data = m.value
    symbols[data['address']] = [data['underlyingAsset']['symbol']]

response = requests.get("https://equilibria.fi/api/bribe-info")
data = response.json()['list'][0]
choiceMap = parse('$..choiceMap').find(data)[0].value
for o in parse('$..options').find(data)[0].value:
    if o['market'] in symbols and (vlEQB := choiceMap.get(str(o['id']))):
        symbols[o['market']].append(vlEQB)
print(symbols)
