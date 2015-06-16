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
import pickle
from flask_sockets import Sockets
import datetime
from flask.ext.seasurf import SeaSurf
import teams, users

secret_key = "a268f42c-f7d7-4475-b8df-8d85a1b417ea"
app = Flask(__name__)
app.debug = True
app.secret_key = secret_key
csrf = SeaSurf(app)

sockets = Sockets(app)

pomodoro_sessions = {
}

recently_active_users = deque(maxlen=10)

connections = defaultdict(lambda: [])

@app.route('/watch/<string:spied_token>', methods=['GET'])
def spy_on_someone(spied_token):
    logged_in = session.get('logged_in_as') == spied_token
    if users.username_exists(spied_token):
        return render_template('spy.html', account_key=spied_token, logged_in=logged_in)
    return render_template('not_found.html', account_key=spied_token), 404

@app.route('/create_account', methods=["POST"])
def create_account():
    username = request.json['username']
    password = request.json['password']
    # Do the username-check inside of transaction
    try:
        users.set_password(username, password)
    except users.AlreadyExists:
        return jsonify(error='already exists'), 403

    session['logged_in_as'] = username
    expiration = datetime.datetime.utcnow() + datetime.timedelta(seconds=300)
    pomodoro_sessions[username] = {
        'expiration': expiration,
        'status': 'busy',
        'notes': 'Busy playing on the internet',
    }

    return jsonify(success=True, new_path=url_for('spy_on_someone', spied_token=username))

@app.route('/login', methods=["POST"])
def login():
    username = request.json['username']
    password = request.json['password']
    if users.valid_login(username, password):
        session['logged_in_as'] = username
        return jsonify(**{'success': True, 'new_path': url_for('spy_on_someone', spied_token=username)})
    else:
        response = jsonify(**{'success': False, 'details': 'invalid credentials'})
        return response, 403

@app.route('/teams/<string:team_name>/watch', methods=["GET"])
def watch_team(team_name):
    return render_template('team_view.html', team_name=team_name, team_members=list(teams.get_team(team_name)['usernames']))

@app.route('/teams', methods=["POST"])
def create_team_view():
    #usernames = request.json['usernames']
    if session.get('logged_in_as') is None:
        return jsonify(error='plz log in'), 403
    username = session['logged_in_as']
    team_name = request.json['team_name']
    try:
        teams.create_team(team_name, username)
    except teams.AlreadyExists:
        return jsonify(error='team already exists'), 400
    except users.NotFound:
        return jsonify(error='user not found'), 404
    return jsonify(success=True, new_path=url_for('watch_team', team_name=team_name))

@app.route('/teams/<string:team_name>/<string:user_name>', methods=["PUT", "DELETE"])
def add_team_member(team_name, user_name):
    if request.method == 'PUT':
        try:
            teams.add_team_member(team_name, user_name)
        except teams.NotFound as e:
            return jsonify(error='team not found'), 404
        except users.NotFound as e:
            return jsonify(error='user not found'), 404
        return jsonify(success=True)
    if request.method == 'DELETE':
        try:
            teams.remove_team_member(team_name, user_name)
        except teams.NotFound as e:
            return jsonify(error='team not found'), 404
        return jsonify(success=True)

# rename me
@app.route('/sessions', methods=["PUT", 'DELETE'])
def pomodoro_sessions_resource():
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

    pomodoro_sessions[username] = {'expiration': expiration, 'status': 'busy', 'notes': notes}
    broadcast_update(username)
    return jsonify(success=True)

def delete_session(username):
    if username not in pomodoro_sessions:
        return render_template('not_found.html', account_key=username, status_code=404)
    del pomodoro_sessions[username]

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

def serializable_session(token):
    session = pomodoro_sessions[token]
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
            if stalked_person in pomodoro_sessions:
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
