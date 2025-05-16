from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# Store users: { sid: { 'id': uuid, 'banned': bool } }
users = {}

# Store banned user_ids here
banned_ids = set()

# Message storage with incremental ID
messages = []
next_msg_id = 1

# Admin password for ban/unban
ADMIN_PASSWORD = "100005"


@app.route('/')
def index():
    # Pass messages to template for initial load
    return render_template('index.html', messages=messages)


@socketio.on('connect')
def handle_connect():
    sid = request.sid
    # Use IP address as user ID (replacing dots with hyphens)
    user_id = request.remote_addr.replace('.', '-')
    users[sid] = {'id': user_id, 'banned': False}
    print(f"User connected with ID {user_id}")


@socketio.on('send_message')
def handle_send_message(data):
    sid = request.sid
    if sid not in users:
        emit('error_message', {'error': 'Unknown user.'})
        return

    if users[sid]['banned']:
        emit('error_message', {'error': 'You are banned and cannot send messages.'})
        return

    global next_msg_id
    username = users[sid]['id']
    message = data.get('message', '').strip()

    if not message:
        return

    msg_id = next_msg_id
    next_msg_id += 1

    messages.append((msg_id, username, message))
    emit('receive_message', {'id': msg_id, 'username': username, 'message': message}, broadcast=True)


@socketio.on('ban_unban_flow')
def handle_ban_unban(data):
    sid = request.sid
    command = data.get('command')
    arg = data.get('arg')
    password = data.get('password')

    if command not in ('ban', 'unban'):
        emit('error_message', {'error': 'Invalid command.'})
        return

    if arg is None:
        user_list = [{'user_id': u['id'], 'banned': u['banned']} for u in users.values()]
        emit('user_list', {'command': command, 'users': user_list})
        return

    if password is None:
        emit('request_password', {'command': command, 'user_id': arg})
        return

    if password != ADMIN_PASSWORD:
        emit('error_message', {'error': 'Incorrect password.'})
        return

    target_sid = None
    for s, u in users.items():
        if u['id'] == arg:
            target_sid = s
            break

    if not target_sid:
        emit('error_message', {'error': f'User ID {arg} not found.'})
        return

    if command == 'ban':
        users[target_sid]['banned'] = True
        banned_ids.add(arg)
        global messages
        messages = [(mid, user, msg) for mid, user, msg in messages if user != arg]
        emit('receive_message', {'id': None, 'username': 'Server', 'message': f"User {arg} has been banned."}, broadcast=True)
        socketio.emit('banned_notification', {'message': 'You have been banned.'}, to=target_sid)
    else:
        users[target_sid]['banned'] = False
        banned_ids.discard(arg)
        emit('success_message', {'message': f"User {arg} unbanned."})
        socketio.emit('unbanned_notification', {'message': 'You have been unbanned.'}, to=target_sid)


@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    if sid in users:
        print(f"User disconnected: {users[sid]['id']}")
        del users[sid]


if __name__ == '__main__':
    socketio.run(app, debug=True)
