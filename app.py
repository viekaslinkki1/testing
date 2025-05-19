from flask import Flask, render_template, session, request, jsonify, redirect, url_for
import sqlite3
import os
import random

app = Flask(__name__)
app.secret_key = 'supersecretkey'

DB_FILE = 'users.db'

# Initialize DB and create users table if not exists
def init_db():
    if not os.path.exists(DB_FILE):
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    coins INTEGER DEFAULT 2000
                )
            ''')
            # Create a default user for testing
            c.execute("INSERT INTO users (username, coins) VALUES (?, ?)", ('testuser', 2000))
            conn.commit()

init_db()

# Simple login for demo
@app.route('/login')
def login():
    session['username'] = 'testuser'
    return redirect(url_for('games'))

# Show Plinko game page
@app.route('/games')
def games():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT coins FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        coins = row[0] if row else 0

    return render_template('games.html', coins=coins)

# Play Plinko
@app.route('/plinko', methods=['POST'])
def plinko():
    username = session.get('username')
    if not username:
        return jsonify({"status": "error", "message": "Not logged in"})

    data = request.get_json() or {}
    slot = data.get('slot')

    prizes = [500, 100, 50, 10, 0, 50, 100, 500]

    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT coins FROM users WHERE username = ?", (username,))
            result = c.fetchone()

            if not result or result[0] < 100:
                return jsonify({"status": "error", "message": "Not enough coins!"})

            coins = result[0] - 100

            # Validate slot index
            if slot is None or not (0 <= slot < len(prizes)):
                prize = 0
            else:
                prize = prizes[slot]

            coins += prize
            outcome = "win" if prize > 0 else "lose"

            c.execute("UPDATE users SET coins = ? WHERE username = ?", (coins, username))
            conn.commit()

            return jsonify({"status": "success", "outcome": outcome, "prize": prize, "new_balance": coins})

    except sqlite3.Error as e:
        return jsonify({"status": "error", "message": f"Database error: {e}"})

if __name__ == '__main__':
    app.run(debug=True)
