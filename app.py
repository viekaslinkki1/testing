import os
import sqlite3
import uuid
from flask import Flask, render_template, request, make_response
from flask_socketio import SocketIO, emit, disconnect
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app)

DB_FILE = 'chat.db'
LOCKED = False
PASSWORD = "100005"
ROLES = {}  # {user_id: "+", "++", "+++"}

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
    user_id = request.cookies.get("user_id")
    if not user_id:
        user_id = str(uuid.uuid4())  # generate permanent ID
    resp = make_response(render_template('index.html', messages=get_messages(), user_id=user_id))
    resp.set_cookie("user_id", user_id, max_age=60*60*24*365)  # 1 year
    return resp

def get_messages():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, user_id, username, message FROM messages ORDER BY id DESC LIMIT 50")
        return c.fetchall()[::-1]  # Show oldest first

@socketio.on('send_message')
def handle_send(data):
    global LOCKED

    user_id = data.get('user_id')
    username = data.get('username', '').strip() or "anom"
    message = data.get('message', '').strip()

    if not user_id or not message:
        return  # Ignore invalid messages

    if LOCKED and not message.startswith("/unlock"):
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '🔒 Chat is currently locked.'}, room=request.sid)
        return

    # Command handling
    if message.startswith("/lock"):
        emit('request_password', {}, room=request.sid)
        return

    if message.startswith("/unlock"):
        if message.strip() == f"/unlock {PASSWORD}":
            LOCKED = False
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '🔓 Chat has been unlocked!'}, broadcast=True)
        else:
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': '❌ Incorrect password.'}, room=request.sid)
        return

    if message == "/role":
        current = ROLES.get(user_id)
        role_display = current if current else "None"
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': f'🎭 Your role is: {role_display}'}, room=request.sid)
        return

    if message in ["/role +", "/role ++", "/role +++"]:
        new_role = message.split()[1]
        ROLES[user_id] = new_role
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': f'✅ Role set to {new_role}'}, room=request.sid)
        return

    # Normal message
    full_message = f"[{user_id[:8]}] {message}"

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO messages (user_id, username, message) VALUES (?, ?, ?)", (user_id, username, full_message))
        message_id = c.lastrowid
        conn.commit()

    emit('receive_message', {'id': message_id, 'username': username, 'message': full_message}, broadcast=True)

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
