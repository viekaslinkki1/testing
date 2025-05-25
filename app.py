from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# In-memory message store
messages = []

@app.route('/')
def index():
    return render_template('index.html', messages=messages)

@socketio.on('send_message')
def handle_send_message(data):
    username = data.get('username', 'anom')
    message = data.get('message', '')
    message_id = str(uuid.uuid4())[:8]  # Short 8-character ID

    messages.append((message_id, username, message))

    emit('receive_message', {
        'id': message_id,
        'username': username,
        'message': message
    }, broadcast=True)

@socketio.on('delete_messages')
def handle_delete_messages(data):
    amount = int(data.get('amount', 0))
    if amount > 0:
        deleted = messages[-amount:]
        deleted_ids = [msg[0] for msg in deleted]
        del messages[-amount:]
        emit('messages_deleted', { 'deleted_ids': deleted_ids }, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)
