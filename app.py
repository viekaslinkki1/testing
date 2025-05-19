import os
import sqlite3
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'

DB_FILE = 'chat.db'
COIN_AMOUNT = 2000
CLAIM_INTERVAL = timedelta(hours=12)

def init_db():
    """ Initialize the database and create tables if they don't exist. """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
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
    """ Display the main page. """
    return render_template('index.html')

@app.route('/games')
def games():
    """ Display the Plinko game. """
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
        winnings = request.json.get('winnings', 0)
        coins += winnings
        
        c.execute("UPDATE users SET coins = ? WHERE username = ?", (coins, username))
        conn.commit()
        return jsonify({"status": "success", "new_balance": coins})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
