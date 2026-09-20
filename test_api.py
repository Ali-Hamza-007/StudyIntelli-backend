import requests
import sys

def test_upload():
    url = 'http://127.0.0.1:8000/api/upload-pdf/'
    
    # We first need to register and get a token
    register_url = 'http://127.0.0.1:8000/api/register/'
    auth_data = {'username': 'testuser123', 'password': 'testpassword123'}
    try:
        r = requests.post(register_url, json=auth_data)
        print("Register:", r.status_code, r.text)
    except Exception as e:
        print("Register error:", e)

    # Let's get token. Wait, there is no login endpoint in urls.py?
    # Let me just check the views.py
    
if __name__ == '__main__':
    test_upload()
