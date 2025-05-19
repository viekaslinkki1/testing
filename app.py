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
    return render_template('index.html')


@app.route('/balance', methods=['GET'])
def get_balance():
    username = session.get('username', 'anom')
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT coins FROM users WHERE username = ?", (username,))
        result = c.fetchone()
    return jsonify({"coins": result[0] if result else 0})


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
        final_slot = path.count(1)
        
        payouts = {0: 0, 1: 0, 2: 1.5, 3: 2, 4: 5}
        multiplier = payouts.get(final_slot, 0)
        winnings = int(bet_amount * multiplier)
        coins += winnings

        c.execute("UPDATE users SET coins = ? WHERE username = ?", (coins, username))
        conn.commit()
        return jsonify({"status": "success", "path": path, "final_slot": final_slot, "winnings": winnings, "new_balance": coins})


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
