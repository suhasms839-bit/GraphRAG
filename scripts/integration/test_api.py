import json, urllib.request, urllib.error

def do_post(url, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print('URL:', url)
            print('STATUS', r.status)
            print(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print('URL:', url)
        print('HTTPError', e.code)
        try:
            print(e.read().decode('utf-8'))
        except:
            print('No body')
    except Exception as e:
        print('URL:', url)
        print('ERROR', e)

base = 'http://localhost:3000/api/auth'
user = {
    'email':'test+bot@example.com',
    'username':'testbot',
    'password':'Testpass123!',
    'full_name':'Test Bot',
    'role':'student'
}

print('Signing up...')
do_post(base + '/signup', user)

print('\nLogging in...')
cred = {'email':user['email'], 'password':user['password']}
do_post(base + '/login', cred)
