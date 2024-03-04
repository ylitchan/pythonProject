from binance.spot import Spot

client = Spot()
print(client.time())

client = Spot(base_url="https://testnet.binance.vision",api_key='1hXMPebjBGCdviwi0hXiUvgoakhVVK54BNxFk5QJ7quopqjoY8z2iNWcDD9U94Sp', api_secret='XasQtYcQHOO4S3bADmdzmvI1Oacdlz5a6RjlBa25EqunSOkPTcxdzFJRojTd4MEz')

# Get account information
client.new_order('ETHUSDT',"BUY","MARKET",quantity=1)
print(client.account())
