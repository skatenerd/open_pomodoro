# open_pomodoro

```
virtualenv -p /usr/bin/python2.7 venv
pip install -r requirements.txt
gunicorn -k flask_sockets.worker -b 0.0.0.0:5001  main:app
```