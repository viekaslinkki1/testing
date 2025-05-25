from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a strong secret key in production

socketio = SocketIO(app)

DATABASE = 'chat.db'

# Chat lock flag
chat_locked = False

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DATABASE):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                message TEXT NOT NULL
            )
        ''')
        # Create default user: username=admin, password=password
        default_username = 'admin'
        default_password = 'password'
        password_hash = generate_password_hash(default_password)
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (default_username, password_hash))
        conn.commit()
        conn.close()
        print("Database initialized with default user 'admin' / 'password'")

# Get all messages as a list of dicts
def get_all_messages():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT id, username, message FROM messages ORDER BY id ASC')
    rows = c.fetchall()
    conn.close()
    messages = [{'id': row['id'], 'username': row['username'], 'message': row['message']} for row in rows]
    return messages

# Authentication required decorator
from functools import wraps
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            error = "Please enter username and password."
        else:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = c.fetchone()
            conn.close()
            if user and check_password_hash(user['password_hash'], password):
                session['username'] = username
                session['user_id'] = user['id']
                return redirect(url_for('index'))
            else:
                error = "Invalid username or password."
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    username = session.get('username')
    user_id = session.get('user_id')
    messages = get_all_messages()
    return render_template('index.html', username=username, user_id=user_id, messages=messages)

@socketio.on('send_message')
def handle_send_message(data):
    global chat_locked
    username = data.get('username', 'anom').strip()
    user_id = data.get('user_id', 'anon_id')
    message = data.get('message', '').strip()

    if chat_locked:
        emit('receive_message', {'id': None, 'username': 'System', 'message': 'Chat is currently locked. Message not sent.'}, room=request.sid)
        return

    if not message:
        return

    # Save message to DB
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO messages (username, message) VALUES (?, ?)', (username, message))
    conn.commit()
    msg_id = c.lastrowid
    conn.close()

    emit('receive_message', {'id': msg_id, 'username': username, 'message': message}, broadcast=True)

@socketio.on('delete_messages')
def handle_delete_messages(data):
    global chat_locked
    if chat_locked:
        emit('receive_message', {'id': None, 'username': 'System', 'message': 'Chat is locked, cannot delete messages.'}, room=request.sid)
        return

    amount = data.get('amount', 0)
    if not isinstance(amount, int) or amount <= 0:
        emit('receive_message', {'id': None, 'username': 'System', 'message': 'Invalid amount for deletion.'}, room=request.sid)
        return

    conn = get_db_connection()
    c = conn.cursor()
    # Fetch last N message IDs to delete
    c.execute('SELECT id FROM messages ORDER BY id DESC LIMIT ?', (amount,))
    rows = c.fetchall()
    if not rows:
        emit('receive_message', {'id': None, 'username': 'System', 'message': 'No messages to delete.'}, room=request.sid)
        conn.close()
        return

    deleted_ids = [row['id'] for row in rows]

    # Delete messages
    c.execute('DELETE FROM messages WHERE id IN ({seq})'.format(
        seq=','.join(['?']*len(deleted_ids))
    ), deleted_ids)
    conn.commit()
    conn.close()

    emit('messages_deleted', {'deleted_ids': deleted_ids}, broadcast=True)
    emit('receive_message', {'id': None, 'username': 'System', 'message': f'Deleted last {len(deleted_ids)} messages.'}, broadcast=True)

# Optional routes for locking/unlocking chat (for admin only)
@app.route('/lock_chat')
@login_required
def lock_chat():
    global chat_locked
    if session.get('username') == 'admin':  # Simple admin check
        chat_locked = True
        return "Chat locked"
    return "Forbidden", 403

@app.route('/unlock_chat')
@login_required
def unlock_chat():
    global chat_locked
    if session.get('username') == 'admin':  # Simple admin check
        chat_locked = False
        return "Chat unlocked"
    return "Forbidden", 403

if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
