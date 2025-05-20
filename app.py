import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
import eventlet
from functools import wraps

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app)

DB_FILE = 'chat.db'

chat_locked = False
awaiting_password = False
awaiting_unlock_password = False

# Emergency messages with sender and message
emergency_messages = [
    {"sender": "Baybars", "text": "Do we have any homework?"},
    {"sender": "Gen", "text": "Idk"},
    {"sender": "Oskar", "text": "i thinkwe have some brainpop"},
    {"sender": "Baybars", "text": "ok thanks"}
]


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT, 
            message TEXT
        )''')
        conn.commit()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == '6767':
            session['logged_in'] = True
        elif password == 'emergency':
            session['logged_in'] = True
            # Delete last 50 messages
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                c.execute("SELECT id FROM messages ORDER BY id DESC LIMIT 50")
                rows = c.fetchall()
                ids = [r[0] for r in rows]
                if ids:
                    c.execute(f"DELETE FROM messages WHERE id IN ({','.join(['?']*len(ids))})", ids)
                    conn.commit()
            # Send emergency message
            preset = emergency_messages[0]  # You can change index or implement selection
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                c.execute("INSERT INTO messages (username, message) VALUES (?, ?)", (preset["sender"], preset["text"]))
                conn.commit()
        else:
            return render_template('login.html', error='Incorrect password.')

        next_page = request.args.get('next')
        return redirect(next_page or url_for('index'))

    return render_template('login.html')


@app.route('/')
@login_required
def index():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, message FROM messages ORDER BY id DESC LIMIT 50")
        messages = c.fetchall()[::-1]
    return render_template('index.html', messages=messages)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


@socketio.on('send_message')
def handle_send(data):
    global chat_locked, awaiting_password, awaiting_unlock_password

    username = data.get('username', '').strip() or "anom"
    message = data.get('message', '').strip()

    if not message:
        return

    if awaiting_password:
        if message == '100005':
            chat_locked = True
            awaiting_password = False
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Chat is now locked.'}, broadcast=True)
        else:
            awaiting_password = False
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Incorrect password. Lock aborted.'}, broadcast=True)
        return

    if awaiting_unlock_password:
        if message == '100005':
            chat_locked = False
            awaiting_unlock_password = False
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Chat unlocked.'}, broadcast=True)
        else:
            awaiting_unlock_password = False
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Incorrect password. Unlock aborted.'}, broadcast=True)
        return

    if message == '/lock':
        awaiting_password = True
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Enter password to lock chat:'})
        return

    if message == '/unlock':
        awaiting_unlock_password = True
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Enter password to unlock chat:'})
        return

    if chat_locked:
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Chat is locked. You cannot send messages.'})
        return

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
