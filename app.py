from flask import Flask, render_template, request, jsonify, session
import sqlite3
from datetime import datetime, timedelta
import random

app = Flask(__name__)
app.secret_key = 'secret'

DB_FILE = 'chat.db'
COIN_AMOUNT = 2000
CLAIM_INTERVAL = timedelta(hours=12)


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            coins INTEGER DEFAULT 0,
            last_claim TIMESTAMP DEFAULT (DATETIME('now', '-1 day'))
        )''')
        conn.commit()


@app.route('/')
def index():
    username = session.get('username', 'anom')
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT coins FROM users WHERE username = ?", (username,))
        result = c.fetchone()
        coins = result[0] if result else 0
    return render_template('index.html', coins=coins)


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
    bet_amount = int(request.json['bet'])
    rows = int(request.json['rows'])

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT coins FROM users WHERE username = ?", (username,))
        result = c.fetchone()

        if not result or result[0] < bet_amount:
            return jsonify({"status": "error", "message": "Not enough coins!"})

        coins = result[0] - bet_amount
        path = [random.choice([-1, 1]) for _ in range(rows)]

        final_slot = path.count(1)  # Count how many times it went right
        payouts = {0: 0, 1: 0, 2: 1.5, 3: 2, 4: 5}  # Modify this to match game logic
        multiplier = payouts.get(final_slot, 0)

        winnings = int(bet_amount * multiplier)
        coins += winnings

        c.execute("UPDATE users SET coins = ? WHERE username = ?", (coins, username))
        conn.commit()
        return jsonify({"status": "success", "path": path, "final_slot": final_slot, "winnings": winnings, "new_balance": coins})


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
