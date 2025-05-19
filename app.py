import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit
import eventlet
from datetime import datetime, timedelta

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app)

DB_FILE = 'chat.db'
PASSWORD = '12345'
COIN_AMOUNT = 2000
CLAIM_INTERVAL = timedelta(hours=12)

def init_db():
    """ Initialize the database and create tables if they don't exist. """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                username TEXT NOT NULL DEFAULT 'anom', 
                message TEXT NOT NULL
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                coins INTEGER DEFAULT 0,
                last_claim TIMESTAMP DEFAULT (DATETIME('now', '-1 day'))
            )''')
            conn.commit()
    except sqlite3.Error as e:
        print(f"Database Error: {e}")

@app.route('/')
def index():
    return redirect(url_for('games'))

@app.route('/games')
def games():
    username = session.get('username', 'anom')
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT coins FROM users WHERE username = ?", (username,))
        result = c.fetchone()
        coins = result[0] if result else 0
    return render_template('games.html', coins=coins)

@app.route('/claim', methods=['POST'])
def claim_coins():
    username = session.get('username', 'anom')
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT coins, last_claim FROM users WHERE username = ?", (username,))
        result = c.fetchone()

        if result:
            last_claim = datetime.strptime(result[1], '%Y-%m-%d %H:%M:%S')
            if datetime.now() - last_claim >= CLAIM_INTERVAL:
                new_balance = result[0] + COIN_AMOUNT
                c.execute("UPDATE users SET coins = ?, last_claim = ? WHERE username = ?",
                          (new_balance, datetime.now(), username))
                conn.commit()
                return jsonify({"status": "success", "new_balance": new_balance})
            else:
                return jsonify({"status": "error", "message": "Too soon to claim again!"})
        else:
            c.execute("INSERT INTO users (username, coins, last_claim) VALUES (?, ?, ?)",
                      (username, COIN_AMOUNT, datetime.now()))
            conn.commit()
            return jsonify({"status": "success", "new_balance": COIN_AMOUNT})

@app.route('/plinko', methods=['POST'])
def plinko():
    username = session.get('username', 'anom')
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT coins FROM users WHERE username = ?", (username,))
        result = c.fetchone()
        
        if not result or result[0] < 100:
            return jsonify({"status": "error", "message": "Not enough coins!"})

        coins = result[0] - 100
        outcome = "lose"
        
        # Random drop logic placeholder (to be implemented later)
        if username == "corner":  # Example condition for winning
            coins += 500
            outcome = "win"
        
        c.execute("UPDATE users SET coins = ? WHERE username = ?", (coins, username))
        conn.commit()
        return jsonify({"status": "success", "outcome": outcome, "new_balance": coins})

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
