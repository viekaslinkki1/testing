from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
app.secret_key = 'your-secret-key'
socketio = SocketIO(app)

messages = []
message_id = 1

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['password'] == 'secret':  # change 'secret' to your real password
            session['logged_in'] = True
            return redirect(url_for('chat'))
        else:
            error = 'Incorrect password'
    return render_template('login.html', error=error)

@app.route('/chat')
def chat():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('chat.html', messages=messages)

@socketio.on('send_message')
def handle_send_message(data):
    global message_id
    msg = {'id': message_id, 'username': data['username'], 'message': data['message']}
    messages.append((message_id, data['username'], data['message']))
    emit('receive_message', msg, broadcast=True)
    message_id += 1

@socketio.on('delete_messages')
def handle_delete_messages(data):
    global messages
    amount = data.get('amount', 0)
    if amount <= 0:
        return
    deleted = messages[-amount:]
    messages = messages[:-amount]
    deleted_ids = [msg[0] for msg in deleted]
    emit('messages_deleted', {'deleted_ids': deleted_ids}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000)
