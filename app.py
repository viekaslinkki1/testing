import os
import sqlite3
import uuid
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, disconnect
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secretkeyhere'  # Change this to a strong secret
socketio = SocketIO(app)

DB_FILE = 'chat.db'

USER_IDS = {}  # sid -> userid
ROLES = {}     # userid -> role

PASSWORD_ON_LOGIN = "6767"
PASSWORD_ROLE_CHANGE = "100005"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT, 
            message TEXT
        )''')
        conn.commit()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == PASSWORD_ON_LOGIN:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Incorrect password, try again.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, message FROM messages ORDER BY id DESC LIMIT 50")
        messages = c.fetchall()[::-1]  # oldest first
    return render_template('index.html', messages=messages)

@socketio.on('connect')
def handle_connect():
    if not session.get('logged_in'):
        # Refuse connection if not logged in
        return False

    sid = request.sid
    if sid not in USER_IDS:
        USER_IDS[sid] = str(uuid.uuid4())[:8]

@socketio.on('send_message')
def handle_send(data):
    sid = request.sid
    if sid not in USER_IDS:
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '⛔ You must be logged in to chat.'}, room=sid)
        return

    userid = USER_IDS[sid]
    message = data.get('message', '').strip()
    if not message:
        return

    # Command handling (same as before)
    if message.startswith('/role'):
        parts = message.split()
        if len(parts) == 1:
            current = ROLES.get(userid, None)
            role_display = current if current else "None"
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': f'🎭 Your role is: {role_display}'}, room=sid)
            return
        elif len(parts) == 2 and parts[1] in ['+', '++', '+++']:
            ROLES[userid] = parts[1]
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': f'✅ Your role set to {parts[1]}'}, room=sid)
            return
        elif len(parts) == 3 and parts[1] in ['+', '++', '+++']:
            role_to_set = parts[1]
            target_prefix = parts[2]
            socketio.emit('request_role_password', {'msg': f'Enter password to set role {role_to_set} for user starting with {target_prefix}', 'role': role_to_set, 'target': target_prefix}, room=sid)
            return
        else:
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '⚠️ Invalid /role command format.'}, room=sid)
            return

    # Normal chat message
    username = userid
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO messages (username, message) VALUES (?, ?)", (username, message))
        message_id = c.lastrowid
        conn.commit()

    emit('receive_message', {'id': message_id, 'username': username, 'message': message}, broadcast=True)

@socketio.on('submit_role_password')
def handle_role_password(data):
    sid = request.sid
    if sid not in USER_IDS:
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '⛔ You must be logged in to chat.'}, room=sid)
        return

    entered_password = data.get('password', '')
    role_to_set = data.get('role', '')
    target_prefix = data.get('target', '')

    if entered_password != PASSWORD_ROLE_CHANGE:
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '❌ Wrong password for role change.'}, room=sid)
        return

    target_id = None
    for uid in USER_IDS.values():
        if uid.startswith(target_prefix):
            target_id = uid
            break

    if target_id is None:
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': f'❌ No user found with ID starting with {target_prefix}.'}, room=sid)
        return

    ROLES[target_id] = role_to_set
    emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': f'✅ Role {role_to_set} set for user {target_id}.'}, broadcast=True)

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
