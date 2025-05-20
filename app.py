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

chat_locked = False
awaiting_password = False
lock_intent = None  # 'lock' or 'unlock'

PRESET_MESSAGES = {
    "emergency": "Baybars said: do we have any homework?",
    "emergency": "Oskar said: i dont think so"
}


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT, 
            message TEXT
        )''')
        conn.commit()


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == '6767':
            session['logged_in'] = True
            next_page = request.args.get('next')
            if not next_page or next_page == '/login':
                return redirect(url_for('index'))
            return redirect(next_page)
        elif password == 'emergency':
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                c.execute("SELECT id FROM messages ORDER BY id DESC LIMIT 50")
                rows = c.fetchall()
                ids_to_delete = [row[0] for row in rows]
                if ids_to_delete:
                    c.execute(f"DELETE FROM messages WHERE id IN ({','.join(['?']*len(ids_to_delete))})", ids_to_delete)
                    conn.commit()
            session['logged_in'] = True
            session['emergency_triggered'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Incorrect password.')
    return render_template('login.html')


@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login', next=request.path))

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, message FROM messages ORDER BY id DESC LIMIT 50")
        messages = c.fetchall()[::-1]

    # Show emergency message if triggered
    emergency_msg = None
    if session.pop('emergency_triggered', False):
        emergency_msg = PRESET_MESSAGES.get("emergency")

    return render_template('index.html', messages=messages, emergency_msg=emergency_msg)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


@socketio.on('send_message')
def handle_send(data):
    global chat_locked, awaiting_password, lock_intent

    username = data.get('username', '').strip() or "anom"
    message = data.get('message', '').strip()

    if not message:
        return

    if awaiting_password:
        if message == '100005':
            chat_locked = (lock_intent == 'lock')
            status = 'locked' if chat_locked else 'unlocked'
            emit('receive_message', {
                'id': 0, 'username': 'SYSTEM',
                'message': f'Chat is now {status}.'
            }, broadcast=True)
        else:
            emit('receive_message', {
                'id': 0, 'username': 'SYSTEM',
                'message': 'Incorrect password. Action aborted.'
            }, broadcast=True)
        awaiting_password = False
        lock_intent = None
        return

    if chat_locked:
        emit('receive_message', {
            'id': 0, 'username': 'SYSTEM',
            'message': 'Chat is locked. You cannot send messages.'
        })
        return

    if message == '/lock':
        awaiting_password = True
        lock_intent = 'lock'
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Enter password to lock chat:'})
        return

    if message == '/unlock':
        awaiting_password = True
        lock_intent = 'unlock'
        emit('receive_message', {'id': 0, 'username': 'SYSTEM', 'message': 'Enter password to unlock chat:'})
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
