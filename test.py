import requests

url = "http://127.0.0.1:8000/webhook"
payload = {
  "qty": 15000,
  "action": "sell",
  "symbol": "1000PEPEUSDT"
}
params = {
    "passphrase": "Armjansk12!!"
}

response = requests.post(url, json=payload, params=params)
print(response.text)