# open_pomodoro

SETUP
=====================
```
virtualenv -p /usr/bin/python2.7 venv
source ./venv/bin/activate
pip install -r requirements.txt
gunicorn -k flask_sockets.worker -b 0.0.0.0:5001  main:app
```
WHY?
=====================
Do you practice the Pomodoro technique?

Do you hate getting interrupted?

Are you happy to be "interrupted" when you are between tasks?

Do you wish people could know *when* to interrupt you?!

What if you could *publish* the state of your Pomodoro timer?

This project will help you do just that.
