import os
import sqlite3
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app)

DB_FILE = 'chat.db'

chat_locked = False  # Global lock state
awaiting_password = False  # To track if server is waiting for password after /lock

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT, 
            message TEXT
        )''')
        conn.commit()

@app.route('/')
def index():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, message FROM messages ORDER BY id DESC LIMIT 50")
        messages = c.fetchall()[::-1]  # Show oldest first
    return render_template('index.html', messages=messages)

@socketio.on('send_message')
def handle_send(data):
    global chat_locked, awaiting_password

    username = data.get('username', '').strip() or "anom"
    message = data.get('message', '').strip()

    if not message:
        return  # Ignore empty messages

    # If server is awaiting password input after /lock
    if awaiting_password:
        if message == '100005':
            chat_locked = True
            awaiting_password = False
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Chat is now locked. Nobody can send messages.'}, broadcast=True)
        else:
            awaiting_password = False
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Incorrect password. Lock aborted.'}, broadcast=True)
        return

    # If chat is locked
    if chat_locked:
        # Only allow /unlock command
        if message == '/unlock':
            chat_locked = False
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Chat unlocked. You can talk now.'}, broadcast=True)
        else:
            # Reject all other messages
            emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Chat is locked. You cannot send messages.'})
        return

    # If not locked, check for /lock command
    if message == '/lock':
        # Ask for password next message
        awaiting_password = True
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Please enter the password to lock chat:'})
        return

    # Normal message: save and broadcast
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
