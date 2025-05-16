import os
import uuid
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='eventlet')

# Store users: { sid: { 'id': uuid, 'real_name': str, 'banned': bool } }
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


@socketio.on('register_user')
def handle_register_user(data):
    sid = request.sid
    real_name = data.get('real_name', '').strip()
    if not real_name:
        emit('register_response', {'success': False, 'error': 'Name cannot be empty'})
        return

    # Generate unique user ID (UUID4 shortened)
    user_id = str(uuid.uuid4())[:8]

    # Save user info
    users[sid] = {'id': user_id, 'real_name': real_name, 'banned': False}

    emit('register_response', {'success': True, 'user_id': user_id, 'real_name': real_name})
    print(f"User registered: {real_name} with ID {user_id}")


@socketio.on('send_message')
def handle_send_message(data):
    sid = request.sid
    if sid not in users:
        emit('error_message', {'error': 'You must register your real name first.'})
        return

    if users[sid]['banned']:
        emit('error_message', {'error': 'You are banned and cannot send messages.'})
        return

    global next_msg_id
    username = data.get('username', 'anom')
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
    command = data.get('command')  # 'ban' or 'unban'
    arg = data.get('arg')          # user_id or None
    password = data.get('password')  # password or None

    # Check if user is registered
    if sid not in users:
        emit('error_message', {'error': 'You must register your real name first.'})
        return

    # Check command validity
    if command not in ('ban', 'unban'):
        emit('error_message', {'error': 'Invalid command.'})
        return

    # Step 1: If no arg, send back user list
    if arg is None:
        # List all users with ID and real name
        user_list = [{'user_id': u['id'], 'real_name': u['real_name'], 'banned': u['banned']} for u in users.values()]
        emit('user_list', {'command': command, 'users': user_list})
        return

    # Step 2: If arg given, but no password -> ask for password
    if password is None:
        emit('request_password', {'command': command, 'user_id': arg})
        return

    # Step 3: Check password
    if password != ADMIN_PASSWORD:
        emit('error_message', {'error': 'Incorrect password.'})
        return

    # Step 4: Ban or unban user by user_id
    target_user_id = arg
    target_sid = None
    for s, u in users.items():
        if u['id'] == target_user_id:
            target_sid = s
            break

    if target_sid is None:
        emit('error_message', {'error': f'User ID {target_user_id} not found.'})
        return

    if command == 'ban':
        users[target_sid]['banned'] = True
        banned_ids.add(target_user_id)
        emit('success_message', {'message': f"User {users[target_sid]['real_name']} (ID: {target_user_id}) banned."})
        # Optionally notify banned user
        socketio.emit('banned_notification', {'message': 'You have been banned.'}, to=target_sid)
    else:
        users[target_sid]['banned'] = False
        banned_ids.discard(target_user_id)
        emit('success_message', {'message': f"User {users[target_sid]['real_name']} (ID: {target_user_id}) unbanned."})
        socketio.emit('unbanned_notification', {'message': 'You have been unbanned.'}, to=target_sid)


@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    if sid in users:
        print(f"User disconnected: {users[sid]['real_name']} ({users[sid]['id']})")
        del users[sid]


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Run using eventlet's WSGI server, binding to 0.0.0.0 and environment PORT
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', port)), app)
