
import os
if not os.path.exists('database.db'):
    import init_db
from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'verlassenen_secret'
DATABASE = 'users.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def cleanup_expired_entries():
    today = date.today()
    weekdays = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, day, created_date FROM entries")
    entries = cur.fetchall()

    for entry in entries:
        created = datetime.strptime(entry['created_date'], '%Y-%m-%d').date()
        entry_day_index = weekdays.index(entry['day'])

        expire_date = created
        while expire_date.weekday() != entry_day_index:
            expire_date += timedelta(days=1)

        if today > expire_date:
            cur.execute("DELETE FROM entries WHERE id = ?", (entry['id'],))

    conn.commit()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM entries WHERE user_id = ?", (session['user_id'],))
    own_entries = cur.fetchall()

    cur.execute("SELECT * FROM characters WHERE user_id = ?", (session['user_id'],))
    characters = cur.fetchall()

    matches = []
    for own in own_entries:
        cur.execute("""
            SELECT entries.*, users.username, characters.char_name FROM entries
            JOIN users ON entries.user_id = users.id
            JOIN characters ON entries.character_id = characters.id
            WHERE entries.user_id != ?
              AND day = ?
              AND keystone = ?
              AND (
                  (start_time <= ? AND end_time >= ?) OR
                  (start_time <= ? AND end_time >= ?) OR
                  (? <= start_time AND ? >= end_time)
              )
        """, (
            session['user_id'], own['day'], own['keystone'],
            own['start_time'], own['start_time'],
            own['end_time'], own['end_time'],
            own['start_time'], own['end_time']
        ))
        for match in cur.fetchall():
            start_overlap = max(own['start_time'], match['start_time'])
            end_overlap = min(own['end_time'], match['end_time'])
            matches.append({
                'username': match['username'],
                'character': match['char_name'],
                'day': match['day'],
                'start': start_overlap,
                'end': end_overlap,
                'spec': match['spec'],
                'keystone': match['keystone']
            })

    return render_template('index.html', own_entries=own_entries, matches=matches, characters=characters)

@app.route('/submit', methods=['POST'])
def submit():
    if 'user_id' not in session:
        return redirect('/login')

    days = request.form.getlist('days')
    start = request.form['start_time']
    end = request.form['end_time']
    spec = request.form['spec']
    keystone = request.form['keystone']
    character_id = request.form['character_id']
    created_date = date.today().isoformat()

    if end <= start:
        return "Ungültiges Zeitfenster: Endzeit darf nicht vor oder gleich Startzeit liegen."

    conn = get_db()
    cur = conn.cursor()

    for day in days:
        # Suche nach überschneidenden Einträgen
        cur.execute("""
            SELECT id FROM entries
            WHERE user_id = ?
              AND character_id = ?
              AND spec = ?
              AND day = ?
              AND (
                  (start_time <= ? AND end_time > ?) OR
                  (start_time < ? AND end_time >= ?) OR
                  (? <= start_time AND ? >= end_time)
              )
        """, (session['user_id'], character_id, spec, day, start, start, end, end, start, end))

        existing = cur.fetchone()
        if existing:
            cur.execute("""
                UPDATE entries SET start_time=?, end_time=?, keystone=?, created_date=?
                WHERE id=?
            """, (start, end, keystone, created_date, existing['id']))
        else:
            cur.execute("""
                INSERT INTO entries (user_id, character_id, day, start_time, end_time, spec, keystone, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session['user_id'], character_id, day, start, end, spec, keystone, created_date))

    conn.commit()
    return redirect('/')

@app.route('/delete_entry/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM entries WHERE id = ? AND user_id = ?", (entry_id, session['user_id']))
    conn.commit()
    return redirect('/')

@app.route('/add_character', methods=['POST'])
def add_character():
    if 'user_id' not in session:
        return redirect('/login')

    char_name = request.form['char_name']
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO characters (user_id, char_name) VALUES (?, ?)", (session['user_id'], char_name))
    conn.commit()
    return redirect('/')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_input = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user['password'], password_input):
            session['user_id'] = user['id']
            return redirect('/')
        return "Login fehlgeschlagen."
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password_raw = request.form['password']
        password_hashed = generate_password_hash(password_raw)
        conn = get_db()
        existing = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            return "Benutzername bereits vergeben."
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password_hashed))
        conn.commit()
        return redirect('/login')
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_db()
    conn.execute("DELETE FROM entries WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM characters WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    session.clear()
    return redirect('/register')

if __name__ == '__main__':
    app.run(debug=True)
