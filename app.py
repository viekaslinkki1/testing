from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
from datetime import datetime, timedelta
import random

app = Flask(__name__)
app.secret_key = 'secret'
DB_FILE = 'chat.db'
COIN_AMOUNT = 2000
CLAIM_INTERVAL = timedelta(hours=12)

# --- DATABASE OPERATIONS ---
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            coins INTEGER DEFAULT 0,
            last_claim TEXT DEFAULT (DATETIME('now', '-1 day'))
        )''')
        conn.commit()

def get_user(username):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT coins, last_claim FROM users WHERE username = ?", (username,))
        return c.fetchone()

def create_user(username):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        last_claim_time = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("INSERT OR IGNORE INTO users (username, coins, last_claim) VALUES (?, ?, ?)",
                  (username, COIN_AMOUNT, last_claim_time))
        conn.commit()


@app.before_request
def ensure_user():
    if 'username' not in session:
        session['username'] = 'user1'
    create_user(session['username'])


@app.route('/')
def home():
    return redirect(url_for('chat'))


@app.route('/chat')
def chat():
    return render_template("chat.html")


@app.route('/balance', methods=['GET'])
def get_balance():
    username = session.get('username')
    user = get_user(username)
    coins = user[0] if user else 0
    return jsonify({"coins": coins})


@app.route('/claim', methods=['POST'])
def claim_coins():
    username = session.get('username')
    user = get_user(username)
    if not user:
        return jsonify({"status": "error", "message": "User not found."})

    coins, last_claim_str = user
    now = datetime.now()
    try:
        last_claim = datetime.strptime(last_claim_str, '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        last_claim = datetime.strptime(last_claim_str, '%Y-%m-%d %H:%M:%S')

    if now - last_claim >= CLAIM_INTERVAL:
        coins += COIN_AMOUNT
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET coins = ?, last_claim = ? WHERE username = ?", (coins, now.strftime('%Y-%m-%d %H:%M:%S'), username))
            conn.commit()
        return jsonify({"status": "success", "message": f"Claimed {COIN_AMOUNT} coins!", "new_balance": coins})
    else:
        time_left = CLAIM_INTERVAL - (now - last_claim)
        return jsonify({"status": "error", "message": f"Wait {str(time_left).split('.')[0]} before claiming again."})


@app.route('/plinko', methods=['POST'])
def plinko():
    username = session.get('username')
    bet_amount = int(request.json.get('bet', 0))
    rows = int(request.json.get('rows', 0))

    user = get_user(username)
    if not user:
        return jsonify({"status": "error", "message": "User not found."})

    coins = user[0]

    if coins < bet_amount or bet_amount <= 0:
        return jsonify({"status": "error", "message": "Not enough coins or invalid bet!"})

    if rows <= 0:
        return jsonify({"status": "error", "message": "Invalid number of rows!"})

    coins -= bet_amount

    # Simulate plinko path
    path = [random.choice([-1, 1]) for _ in range(rows)]
    final_slot = path.count(1)

    # Example payout table
    payouts = {0: 0, 1: 0, 2: 1.5, 3: 2, 4: 5}
    multiplier = payouts.get(final_slot, 0)
    winnings = int(bet_amount * multiplier)
    coins += winnings

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET coins = ? WHERE username = ?", (coins, username))
        conn.commit()

    return jsonify({"status": "success", "path": path, "final_slot": final_slot, "winnings": winnings, "new_balance": coins})


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
