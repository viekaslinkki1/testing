import os
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, session, g
from flask_socketio import SocketIO, emit
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'
socketio = SocketIO(app)

DB_PATH = 'chat.db'

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
        if password == 'pretzel':
            session.clear()
            session['authenticated'] = True
            session['just_logged_in'] = True  # allow one time chat access
            return redirect('/chat')
        return render_template('login.html', error="Wrong password.")
    return render_template('login.html')

@app.route('/chat')
def chat():
    if not session.get('authenticated'):
        return redirect('/login')
    if session.get('just_logged_in') != True:
        session.clear()
        return redirect('/login')
    session['just_logged_in'] = False  # reset after first access

    db = get_db()
    cur = db.execute('SELECT * FROM messages ORDER BY id ASC')
    messages = cur.fetchall()
    return render_template('index.html', messages=messages)

locked = False
LOCK_PASSWORD = "100005"

@socketio.on('send_message')
def handle_message(data):
    global locked
    username = data['username']
    message = data['message'].strip()

    # Check if chat is locked
    if locked:
        if message.startswith('/unlock '):
            pw = message.split(' ', 1)[1]
            if pw == LOCK_PASSWORD:
                locked = False
                emit('receive_message', {'id': None, 'username': 'System', 'message': 'Chat unlocked!'}, broadcast=True)
            else:
                emit('receive_message', {'id': None, 'username': 'System', 'message': 'Wrong unlock password.'}, room=request.sid)
            return
        else:
            emit('receive_message', {'id': None, 'username': 'System', 'message': 'Chat is locked. Use /unlock <password> to unlock.'}, room=request.sid)
            return

    # Emergency commands
    if message == '/emergency123':
        db = get_db()
        # Delete all messages
        db.execute('DELETE FROM messages')
        db.commit()
        # Insert special message
        db.execute('INSERT INTO messages (username, message) VALUES (?, ?)', ('baybars', 'do we have any homework'))
        db.commit()
        msg_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        # Broadcast the clear and the new message
        emit('messages_deleted', {'deleted_ids': []}, broadcast=True)  # front end can clear all when empty list?
        emit('receive_message', {'id': msg_id, 'username': 'baybars', 'message': 'do we have any homework'}, broadcast=True)
        return

    if message == '/lock':
        # Ask for password to lock chat
        emit('receive_message', {'id': None, 'username': 'System', 'message': 'Please type /lock <password> to lock the chat.'}, room=request.sid)
        return

    if message.startswith('/lock '):
        pw = message.split(' ', 1)[1]
        if pw == LOCK_PASSWORD:
            locked = True
            emit('receive_message', {'id': None, 'username': 'System', 'message': 'Chat locked! No one can send messages now.'}, broadcast=True)
        else:
            emit('receive_message', {'id': None, 'username': 'System', 'message': 'Wrong lock password.'}, room=request.sid)
        return

    # Normal message insert
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
