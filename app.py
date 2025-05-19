import os
import sqlite3
from flask import Flask, render_template, request, session, jsonify
from flask_socketio import SocketIO
import eventlet
from datetime import datetime, timedelta

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
socketio = SocketIO(app)

DB_FILE = 'chat.db'
COIN_AMOUNT = 2000
CLAIM_INTERVAL = timedelta(hours=12)


def init_db():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL DEFAULT 'anom',
                    message TEXT NOT NULL
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    coins INTEGER DEFAULT 0,
                    last_claim TIMESTAMP DEFAULT (DATETIME('now', '-1 day'))
                )
            ''')
            conn.commit()
    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")


# Run this once at import to make sure tables exist
init_db()


@app.route('/')
def index():
    # Just a simple landing page or redirect to games for testing
    return "Welcome! Go to /games"


@app.route('/games')
def games():
    username = session.get('username', 'anom')
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT coins FROM users WHERE username = ?", (username,))
            result = c.fetchone()
            coins = result[0] if result else 0
        return render_template('games.html', coins=coins)
    except sqlite3.Error as e:
        return f"Database error: {e}", 500


@app.route('/claim', methods=['POST'])
def claim_coins():
    username = session.get('username', 'anom')
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT coins, last_claim FROM users WHERE username = ?", (username,))
            result = c.fetchone()

            now = datetime.now()
            if result:
                last_claim = datetime.strptime(result[1], '%Y-%m-%d %H:%M:%S')
                if now - last_claim >= CLAIM_INTERVAL:
                    new_balance = result[0] + COIN_AMOUNT
                    c.execute("UPDATE users SET coins = ?, last_claim = ? WHERE username = ?",
                              (new_balance, now.strftime('%Y-%m-%d %H:%M:%S'), username))
                    conn.commit()
                    return jsonify({"status": "success", "new_balance": new_balance})
                else:
                    return jsonify({"status": "error", "message": "Too soon to claim again!"})
            else:
                c.execute("INSERT INTO users (username, coins, last_claim) VALUES (?, ?, ?)",
                          (username, COIN_AMOUNT, now.strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
                return jsonify({"status": "success", "new_balance": COIN_AMOUNT})
    except sqlite3.Error as e:
        return jsonify({"status": "error", "message": f"Database error: {e}"})


@app.route('/plinko', methods=['POST'])
def plinko():
    username = session.get('username', 'anom')
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT coins FROM users WHERE username = ?", (username,))
            result = c.fetchone()

            if not result or result[0] < 100:
                return jsonify({"status": "error", "message": "Not enough coins!"})

            coins = result[0] - 100
            outcome = "lose"

            # TODO: Add real randomness here or from client
            import random
            drop_position = random.randint(0, 10)  # Example drop position
            if drop_position in [0, 10]:  # Corners win big
                coins += 500
                outcome = "win"
            elif drop_position in [4, 5, 6]:  # Middle drop small win
                coins += 150
                outcome = "win"

            c.execute("UPDATE users SET coins = ? WHERE username = ?", (coins, username))
            conn.commit()
            return jsonify({"status": "success", "outcome": outcome, "new_balance": coins})
    except sqlite3.Error as e:
        return jsonify({"status": "error", "message": f"Database error: {e}"})


if __name__ == '__main__':
    # Use eventlet for SocketIO in dev mode
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
