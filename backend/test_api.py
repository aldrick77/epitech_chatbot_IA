import urllib.request as r
import json
import sys

url = 'https://epitech-chatbot.onrender.com/chat'
data = json.dumps({"message": "Quelles sont les formations ?", "session_id": "test"}).encode('utf-8')
req = r.Request(url, method='POST', data=data, headers={'Content-Type':'application/json'})

try:
    with r.urlopen(req) as res:
        print(res.read().decode('utf-8'))
except Exception as e:
    print(e)
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
