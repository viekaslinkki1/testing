import os
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# Store users: { sid: { 'id': uuid, 'real_name': str, 'banned': bool } }
users = {}
banned_ids = set()
messages = []
next_msg_id = 1
ADMIN_PASSWORD = "100005"

@app.route('/')
def index():
    return render_template('index.html', messages=messages)

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
    username = users[sid]['id']
    message = data.get('message', '').strip()

    if not message:
        return

    msg_id = next_msg_id
    next_msg_id += 1

    messages.append((msg_id, username, message))

    emit('receive_message', {'id': msg_id, 'username': username, 'message': message}, broadcast=True)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    if sid in users:
        print(f"User disconnected: {users[sid]['id']}")
        del users[sid]

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
