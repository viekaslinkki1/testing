from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app)

# Ensure the database exists
if not os.path.exists('chat.db'):
    with sqlite3.connect('chat.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, message TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

def get_recent_messages(limit=50):
    with sqlite3.connect('chat.db') as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, message FROM messages ORDER BY id DESC LIMIT ?", (limit,))
        return reversed(c.fetchall())  # Reverse to display oldest at top

@app.route('/')
def index():
    messages = get_recent_messages()
    return render_template('index.html', messages=messages)

@socketio.on('send_message')
def handle_send(data):
    username = data['username']
    message = data['message']

    with sqlite3.connect('chat.db') as conn:
        c = conn.cursor()
        c.execute("INSERT INTO messages (username, message) VALUES (?, ?)", (username, message))
        msg_id = c.lastrowid
        conn.commit()

    emit('receive_message', {'id': msg_id, 'username': username, 'message': message}, broadcast=True)

@socketio.on('delete_messages')
def handle_delete(data):
    amount = data.get('amount', 0)
    with sqlite3.connect('chat.db') as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM messages ORDER BY id DESC LIMIT ?", (amount,))
        rows = c.fetchall()
        ids_to_delete = [row[0] for row in rows]

        if ids_to_delete:
            c.execute("DELETE FROM messages WHERE id IN ({seq})".format(
                seq=','.join(['?'] * len(ids_to_delete))), ids_to_delete)
            conn.commit()

    emit('messages_deleted', {'deleted_ids': ids_to_delete}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)
