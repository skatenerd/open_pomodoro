from flask import (
    Flask,
    request,
    session,
    render_template,
    jsonify,
    #g,
    redirect,
    url_for,
    #abort,
)
import gevent
from collections import namedtuple, defaultdict, deque
import json
import hashlib
import pickle
from flask_sockets import Sockets
import datetime
import os
from flask.ext.seasurf import SeaSurf
import tempfile

secret_key = "a268f42c-f7d7-4475-b8df-8d85a1b417ea"
salt = "abcdabcdabcdabcdabcdabcdabcdabcd"
database_path = 'accounts_database.txt'

app = Flask(__name__)
app.debug = True
app.secret_key = secret_key
csrf = SeaSurf(app)

sockets = Sockets(app)

sessions = {
}

recently_active_users = deque(maxlen=10)

connections = defaultdict(lambda: [])

def initialize_file_database(path):
    if not os.path.isfile(path):
        with open(path, 'w') as f:
            pickle.dump({}, f)

initialize_file_database(database_path)

@app.route('/watch/<string:spied_token>', methods=['GET'])
def spy_on_someone(spied_token):
    logged_in = session.get('logged_in_as') == spied_token
    if spied_token in get_database_contents(database_path):
        return render_template('spy.html', account_key=spied_token, logged_in=logged_in)
    return render_template('not_found.html', account_key=spied_token, status_code=404)

def set_password(username, password):
    def transform_database(database):
        database[username] = hash_password(password)
        return database
    transform_file(database_path, transform_database)

def username_exists(username):
    return username in get_database_contents(database_path)

@app.route('/create_account', methods=["POST"])
def create_account():
    username = request.values['username']
    password = request.values['password']
    if not username_exists(username):
        session['logged_in_as'] = username
        set_password(username, password)
        sessions[username] = 'Busy playing on the internet'
        return jsonify(**{'success': True, 'new_path': url_for('spy_on_someone', spied_token=username)})
    else:
        response = jsonify(**{'success': False, 'details': 'already exists'})
        response.status_code = 403
        return response

@app.route('/login', methods=["POST"])
def login():
    username = request.values['username']
    password = request.values['password']
    if valid_login(username, password):
        session['logged_in_as'] = username
        return jsonify(**{'success': True, 'new_path': url_for('spy_on_someone', spied_token=username)})
    else:
        response = jsonify(**{'success': False, 'details': 'invalid credentials'})
        response.status_code = 403
        return response

@app.route('/sessions', methods=["PUT", 'DELETE'])
def sessions_resource():
    if session.get('logged_in_as') is None:
        return render_template('front.html')

    username = session['logged_in_as']

    if username not in recently_active_users:
        recently_active_users.appendleft(username)

    if request.method == 'PUT':
        return put_session(username, request)
    if request.method == 'DELETE':
        return delete_session(username)

def put_session(username, request):
    notes = request.json['notes']
    duration = request.json['duration']

    expiration = datetime.datetime.utcnow() + datetime.timedelta(seconds=duration)

    sessions[username] = {'expiration': expiration, 'status': 'busy', 'notes': notes}
    broadcast_update(username)
    return jsonify(success=True)

def delete_session(username):
    if username not in sessions:
        return render_template('not_found.html', account_key=username, status_code=404)
    del sessions[username]

    for stalker in connections[username]:
        if not stalker.closed:
            stalker.send(json.dumps({'type': 'session_delete', 'body': {'token': username}}))

    return jsonify(success=True)

@app.route('/', methods=["GET"])
def front():
    return render_template('front.html', recently_active=recently_active_users, current_user=session.get('logged_in_as'))

@app.route('/logout', methods=["POST", 'GET'])
def logout():
    session['logged_in_as'] = None
    return redirect(url_for('front'))

def valid_login(username, password):
    with open(database_path) as f:
        accounts = pickle.load(f)
    return accounts.get(username) == hash_password(password)

def hash_password(password):
    return hashlib.sha512(password + salt).hexdigest()

def serializable_session(token):
    session = sessions[token]
    serializable = dict(session)
    serializable['expiration'] = "%sZ"%session['expiration'].isoformat()
    serializable['token'] = token
    return serializable

def session_as_string(token):
    return json.dumps(serializable_session(token))

def broadcast_update(stalked_person):
    message = session_as_string(stalked_person)
    for stalker in connections[stalked_person]:
        if not stalker.closed:
            stalker.send(json.dumps({'type': 'session_refresh', 'body': serializable_session(stalked_person)}))

@sockets.route('/listen')
def inbox(ws):
    for stalked_person in socket_values(ws):
        if stalked_person:
            connections[stalked_person].append(ws)
            if stalked_person in sessions:
                if not ws.closed:
                    ws.send(json.dumps({'type': 'session_refresh', 'body': serializable_session(stalked_person)}))
    remove_client(ws)

def socket_values(socket):
    while not socket.closed:
        # Sleep to prevent *contstant* context-switches.
        gevent.sleep()
        yield socket.receive()

def remove_client(client_socket):
    for listener_list in connections.values():
        if client_socket in listener_list:
            listener_list.remove(client_socket)

db_write_lock = gevent.lock.Semaphore()

def get_database_contents(path):
    with open(path, 'r') as f:
        contents = pickle.load(f)
    return contents

def write_database_contents(contents, path):
    with tempfile.NamedTemporaryFile(delete=False) as out_tmp:
        pickle.dump(contents, out_tmp)
        os.rename(out_tmp.name, path)

def transform_file(path, transformation):
    try:
        db_write_lock.acquire()
        contents = get_database_contents(path)
        new_contents = transformation(contents)
        write_database_contents(new_contents, path)
    finally:
        db_write_lock.release()
