import os
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect
from flask_socketio import SocketIO, emit
import sqlite3
from datetime import datetime
from flask import g

app = Flask(__name__)
socketio = SocketIO(app)

DB_PATH = 'chat.db'

# Main and emergency password
UNIVERSAL_PASSWORD = "pretzel"
EMERGENCY_PASSWORD = "emergency123"

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            message TEXT NOT NULL
        )
    ''')
    db.commit()

@app.route('/')
def index():
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        db = get_db()

        if password == EMERGENCY_PASSWORD:
            # Delete all messages
            db.execute('DELETE FROM messages')
            db.commit()

            # Add emergency message
            db.execute('INSERT INTO messages (username, message) VALUES (?, ?)', ("baybars", "do we have any homework"))
            db.commit()

            cur = db.execute('SELECT * FROM messages ORDER BY id ASC')
            messages = cur.fetchall()
            return render_template('index.html', messages=messages)

        elif password == UNIVERSAL_PASSWORD:
            cur = db.execute('SELECT * FROM messages ORDER BY id ASC')
            messages = cur.fetchall()
            return render_template('index.html', messages=messages)

        return render_template('login.html', error="Wrong password.")
    return render_template('login.html')

@app.route('/chat')
def chat():
    return redirect('/login')  # always force login first

@socketio.on('send_message')
def handle_message(data):
    username = data['username']
    message = data['message']
    db = get_db()
    db.execute('INSERT INTO messages (username, message) VALUES (?, ?)', (username, message))
    db.commit()
    msg_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    emit('receive_message', {'id': msg_id, 'username': username, 'message': message}, broadcast=True)

@socketio.on('delete_messages')
def delete_messages(data):
    amount = int(data.get('amount', 0))
    db = get_db()
    cur = db.execute('SELECT id FROM messages ORDER BY id DESC LIMIT ?', (amount,))
    rows = cur.fetchall()
    deleted_ids = [r[0] for r in rows]
    db.executemany('DELETE FROM messages WHERE id=?', [(i,) for i in deleted_ids])
    db.commit()
    emit('messages_deleted', {'deleted_ids': deleted_ids}, broadcast=True)

if __name__ == '__main__':
    with app.app_context():
        init_db()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
