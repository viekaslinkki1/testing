import os
import sqlite3
import uuid
from flask import Flask, render_template, request, make_response
from flask_socketio import SocketIO, emit
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app)

DB_FILE = 'chat.db'
user_ids = {}       # sid -> user_id
user_roles = {}     # user_id -> role
global_locked = False
LOCK_PASSWORD = "100005"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT, 
            message TEXT
        )''')
        conn.commit()

def get_messages():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, message FROM messages ORDER BY id DESC LIMIT 50")
        return c.fetchall()[::-1]

@app.route('/')
def index():
    user_id = request.cookies.get('user_id')
    if not user_id:
        user_id = str(uuid.uuid4())[:6]
        resp = make_response(render_template('index.html', messages=get_messages()))
        resp.set_cookie('user_id', user_id, max_age=60*60*24*365)
        return resp
    return render_template('index.html', messages=get_messages())

@socketio.on('connect')
def handle_connect():
    user_id = request.cookies.get('user_id')
    if not user_id:
        user_id = str(uuid.uuid4())[:6]
    user_ids[request.sid] = user_id
    if user_id not in user_roles:
        user_roles[user_id] = ''
    emit('your_id', {'user_id': user_id})
    print(f"[Connected] {request.sid} -> {user_id}")

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in user_ids:
        print(f"[Disconnected] {request.sid} -> {user_ids[request.sid]}")
        del user_ids[request.sid]

@socketio.on('send_message')
def handle_send(data):
    global global_locked
    user_id = user_ids.get(request.sid, 'unknown')
    message = data.get('message', '').strip()

    if not message:
        return

    # Command: /lock
    if message.startswith('/lock'):
        args = message.split()
        if len(args) == 2 and args[1] == LOCK_PASSWORD:
            global_locked = True
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '🔒 Chat has been locked.'}, broadcast=True)
        else:
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '❌ Incorrect password.'}, room=request.sid)
        return

    # Command: /unlock
    if message.startswith('/unlock'):
        global_locked = False
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '🔓 Chat has been unlocked.'}, broadcast=True)
        return

    # Command: /role
    if message.startswith('/role'):
        args = message.split()
        if len(args) == 2 and args[1] in ['+', '++', '+++']:
            user_roles[user_id] = args[1]
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': f'✅ Your role is now {args[1]}'}, room=request.sid)
        else:
            current = user_roles.get(user_id, '')
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': f'🎭 Your role is: {current or \"None\"}'}, room=request.sid)
        return

    # If chat is locked, block all other messages
    if global_locked:
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '🔒 Chat is currently locked. Try again later.'}, room=request.sid)
        return

    username = f"{user_id}{' ' + user_roles.get(user_id, '') if user_roles.get(user_id) else ''}"

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO messages (username, message) VALUES (?, ?)", (username, message))
        message_id = c.lastrowid
        conn.commit()

    emit('receive_message', {'id': message_id, 'username': username, 'message': message}, broadcast=True)

@socketio.on('delete_messages')
def handle_delete_messages(data):
    amount = data.get('amount', 0)
    if not isinstance(amount, int) or amount <= 0:
        return

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM messages ORDER BY id DESC LIMIT ?", (amount,))
        rows = c.fetchall()
        ids_to_delete = [row[0] for row in rows]

        if ids_to_delete:
            c.execute(f"DELETE FROM messages WHERE id IN ({','.join(['?']*len(ids_to_delete))})", ids_to_delete)
            conn.commit()

    emit('messages_deleted', {'deleted_ids': ids_to_delete}, broadcast=True)

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
