import os
import sqlite3
import uuid
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app)

DB_FILE = 'chat.db'
PASSWORD = "100005"

LOCKED = False  # Global chat lock flag
ROLES = {}      # user_id -> role mapping
USER_IDS = {}   # sid -> user_id mapping

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id TEXT,
            username TEXT, 
            message TEXT
        )''')
        conn.commit()

@app.route('/')
def index():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, user_id, username, message FROM messages ORDER BY id DESC LIMIT 50")
        messages = c.fetchall()[::-1]  # Show oldest first
    return render_template('index.html', messages=messages)

@socketio.on('connect')
def on_connect():
    # Assign a permanent user_id for this connection
    user_id = str(uuid.uuid4())
    USER_IDS[request.sid] = user_id
    emit('your_id', {'user_id': user_id})

@socketio.on('disconnect')
def on_disconnect():
    # Remove stored user_id on disconnect
    if request.sid in USER_IDS:
        USER_IDS.pop(request.sid)

@socketio.on('send_message')
def handle_send(data):
    username = data.get('username', '').strip() or "anom"
    message = data.get('message')
    user_id = USER_IDS.get(request.sid)

    if not message or message.strip() == "":
        return  # Ignore empty

    # Handle commands
    if message.startswith("/lock"):
        emit('receive_message', {'id': 0, 'username': username, 'message': f"[{user_id[:8]}] {message}"}, broadcast=True)
        # Request password from user to lock chat
        emit('request_password', {}, room=request.sid)
        return

    if message.startswith("/unlock"):
        emit('receive_message', {'id': 0, 'username': username, 'message': f"[{user_id[:8]}] {message}"}, broadcast=True)
        # Expect /unlock 100005 exactly
        if message.strip() == f"/unlock {PASSWORD}":
            global LOCKED
            LOCKED = False
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '🔓 Chat has been unlocked!'}, broadcast=True)
        else:
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '❌ Incorrect password.'}, room=request.sid)
        return

    if LOCKED:
        # If locked, no one except "SYSTEM" can send messages (commands handled above)
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '🚫 Chat is locked. You cannot send messages.'}, room=request.sid)
        return

    if message == "/role":
        emit('receive_message', {'id': 0, 'username': username, 'message': f"[{user_id[:8]}] {message}"}, broadcast=True)
        current = ROLES.get(user_id)
        role_display = current if current else "None"
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': f'🎭 Your role is: {role_display}'}, room=request.sid)
        return

    if message in ["/role +", "/role ++", "/role +++"]:
        emit('receive_message', {'id': 0, 'username': username, 'message': f"[{user_id[:8]}] {message}"}, broadcast=True)
        new_role = message.split()[1]
        ROLES[user_id] = new_role
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': f'✅ Role set to {new_role}'}, room=request.sid)
        return

    # Normal message saving & broadcasting
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO messages (user_id, username, message) VALUES (?, ?, ?)", (user_id, username, message))
        message_id = c.lastrowid
        conn.commit()

    emit('receive_message', {'id': message_id, 'username': username, 'message': f"[{user_id[:8]}] {message}"}, broadcast=True)

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
