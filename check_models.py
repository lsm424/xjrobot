import requests

url = "http://47.108.93.204:11435/api/tags"

response = requests.get(url)
if response.status_code == 200:
    models = response.json()
   