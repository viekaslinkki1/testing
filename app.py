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
LOCK_PASSWORD = "100005"

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
    db.execute('''
        CREATE TABLE IF NOT EXISTS login (
            password TEXT NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS status (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    # Default password if empty
    if not db.execute('SELECT * FROM login').fetchone():
        db.execute('INSERT INTO login (password) VALUES (?)', ('pretzel',))
    # Default lock status
    if not db.execute("SELECT * FROM status WHERE key = 'locked'").fetchone():
        db.execute("INSERT INTO status (key, value) VALUES ('locked', 'false')")
    db.commit()

@app.route('/')
def index():
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    db = get_db()
    if request.method == 'POST':
        password = request.form['password']
        data = db.execute('SELECT password FROM login').fetchone()
        if data and password == data[0]:
            session['authenticated'] = True
            return redirect('/chat')
        return render_template('login.html', error="Wrong password.")
    return render_template('login.html')

@app.route('/chat')
def chat():
    if not session.get('authenticated'):
        return redirect('/login')
    db = get_db()
    cur = db.execute('SELECT * FROM messages ORDER BY id ASC')
    messages = cur.fetchall()
    return render_template('index.html', messages=messages)

@app.route('/lock', methods=['GET', 'POST'])
def lock():
    if request.method == 'POST':
        password = request.form['password']
        if password == LOCK_PASSWORD:
            db = get_db()
            db.execute("UPDATE status SET value='true' WHERE key='locked'")
            db.commit()
            return "Chat locked successfully."
        return "Wrong password."
    return '''
        <form method="post">
            Password: <input type="password" name="password">
            <input type="submit" value="Lock Chat">
        </form>
    '''

@app.route('/unlock', methods=['GET', 'POST'])
def unlock():
    if request.method == 'POST':
        password = request.form['password']
        if password == LOCK_PASSWORD:
            db = get_db()
            db.execute("UPDATE status SET value='false' WHERE key='locked'")
            db.commit()
            return "Chat unlocked successfully."
        return "Wrong password."
    return '''
        <form method="post">
            Password: <input type="password" name="password">
            <input type="submit" value="Unlock Chat">
        </form>
    '''

@socketio.on('send_message')
def handle_message(data):
    db = get_db()
    lock_status = db.execute("SELECT value FROM status WHERE key='locked'").fetchone()
    if lock_status and lock_status[0] == 'true':
        emit('receive_message', {'id': -1, 'username': 'System', 'message': 'Chat is currently locked.'}, room=request.sid)
        return
    username = data['username']
    message = data['message']
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
