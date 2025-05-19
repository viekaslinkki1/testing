from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# Global state for chat lock
chat_locked = False
locker_user_id = None

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def on_connect():
    print(f'User connected: {request.sid}')
    emit('status', {'msg': 'Connected to chat server'})

@socketio.on('send_message')
def handle_message(data):
    global chat_locked, locker_user_id

    user_id = data.get('user_id')
    message = data.get('message')

    if not user_id or not message:
        emit('error', {'msg': 'Invalid message data'}, room=request.sid)
        return

    # If chat is locked, block all users except the locker
    if chat_locked and user_id != locker_user_id:
        emit('error', {'msg': 'Chat is locked. You cannot send messages now.'}, room=request.sid)
        return

    # Commands processing
    if message.strip() == '/lock':
        # Ask user for password via prompt_password event
        emit('prompt_password', {'msg': 'Enter password to lock chat:'}, room=request.sid)
        return

    if message.strip() == '/unlock':
        if user_id == locker_user_id:
            # Unlock the chat
            chat_locked = False
            locker_user_id = None
            emit('chat_unlocked', {'msg': 'Chat has been unlocked.'}, broadcast=True)
        else:
            emit('error', {'msg': 'Only the locker can unlock the chat.'}, room=request.sid)
        return

    # Normal message broadcast
    emit('new_message', {'user': user_id, 'msg': message}, broadcast=True)


@socketio.on('lock_password')
def handle_lock_password(data):
    global chat_locked, locker_user_id

    user_id = data.get('user_id')
    password = data.get('password')

    if not user_id or password is None:
        emit('error', {'msg': 'Invalid password data'}, room=request.sid)
        return

    if password == '100005':
        chat_locked = True
        locker_user_id = user_id
        emit('chat_locked', {'msg': 'Chat locked! Only you can send messages now.'}, broadcast=True)
    else:
        emit('error', {'msg': 'Wrong password. Chat remains unlocked.'}, room=request.sid)


if __name__ == '__main__':
    socketio.run(app, debug=True)
