import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app)

DB_FILE = 'chat.db'
PASSWORD = '12345'  # Password for access


def init_db():
    """ Initialize the database and create the messages table if it doesn't exist. """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                username TEXT NOT NULL DEFAULT 'anom', 
                message TEXT NOT NULL
            )''')
            conn.commit()
    except sqlite3.Error as e:
        print(f"Database Error: {e}")


@app.route('/', methods=['GET', 'POST'])
def password_protect():
    if request.method == 'POST':
        if request.form.get('password') == PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/chat')
def index():
    if not session.get('authenticated'):
        return redirect(url_for('password_protect'))
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT id, username, message FROM messages ORDER BY id DESC LIMIT 50")
            messages = c.fetchall()[::-1]
    except sqlite3.Error as e:
        print(f"Database Error: {e}")
        messages = []
    return render_template('index.html', messages=messages)


@app.route('/games')
def games():
    return render_template('games.html')


@socketio.on('send_message')
def handle_send(data):
    """ Handle incoming chat messages and broadcast them to all clients. """
    username = data.get('username', 'anom').strip()
    message = data.get('message')

    if not message or message.strip() == "":
        return

    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO messages (username, message) VALUES (?, ?)", (username, message))
            message_id = c.lastrowid
            conn.commit()
    except sqlite3.Error as e:
        print(f"Database Error: {e}")
        return

    emit('receive_message', {'id': message_id, 'username': username, 'message': message}, broadcast=True)


@socketio.on('delete_messages')
def handle_delete_messages(data):
    """ Handle deletion of the latest specified number of messages. """
    amount = data.get('amount', 0)
    if not isinstance(amount, int) or amount <= 0:
        return

    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM messages ORDER BY id DESC LIMIT ?", (amount,))
            rows = c.fetchall()
            ids_to_delete = [row[0] for row in rows]

            if ids_to_delete:
                query = f"DELETE FROM messages WHERE id IN ({','.join(['?'] * len(ids_to_delete))})"
                c.execute(query, ids_to_delete)
                conn.commit()
    except sqlite3.Error as e:
        print(f"Database Error: {e}")
        return

    emit('messages_deleted', {'deleted_ids': ids_to_delete}, broadcast=True)


if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
