
import os
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.secret_key = 'verlassenen_secret'

# Datenbankkonfiguration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL').replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

with app.app_context():
    db.create_all()

# ---------------- Datenbank-Modelle ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.String, nullable=False)
    characters = db.relationship('Character', backref='user', cascade="all, delete")

class Character(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    char_name = db.Column(db.String, nullable=False)
    entries = db.relationship('Entry', backref='character', cascade="all, delete")

class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey('character.id'), nullable=False)
    day = db.Column(db.String, nullable=False)
    start_time = db.Column(db.String, nullable=False)
    end_time = db.Column(db.String, nullable=False)
    spec = db.Column(db.String, nullable=False)
    keystone = db.Column(db.String, nullable=False)
    created_date = db.Column(db.String, nullable=False)

# ---------------- Hilfsfunktionen ----------------

@app.before_request
def cleanup_expired_entries():
    today = date.today()
    weekdays = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    entries = Entry.query.all()

    for entry in entries:
        created = datetime.strptime(entry.created_date, '%Y-%m-%d').date()
        entry_day_index = weekdays.index(entry.day)
        expire_date = created
        while expire_date.weekday() != entry_day_index:
            expire_date += timedelta(days=1)
        if today > expire_date:
            db.session.delete(entry)
    db.session.commit()

# ---------------- Routen ----------------
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')

    own_entries = Entry.query.filter_by(user_id=session['user_id']).all()
    characters = Character.query.filter_by(user_id=session['user_id']).all()
    matches = []

    for own in own_entries:
        overlaps = Entry.query.filter(
            Entry.user_id != session['user_id'],
            Entry.day == own.day,
            Entry.keystone == own.keystone,
            db.or_(
                db.and_(Entry.start_time <= own.start_time, Entry.end_time > own.start_time),
                db.and_(Entry.start_time < own.end_time, Entry.end_time >= own.end_time),
                db.and_(Entry.start_time >= own.start_time, Entry.end_time <= own.end_time)
            )
        ).join(User, Entry.user_id == User.id).join(Character, Entry.character_id == Character.id).add_columns(
            User.username, Character.char_name, Entry.day, Entry.start_time, Entry.end_time, Entry.spec, Entry.keystone
        ).all()

        for m in overlaps:
            start_overlap = max(own.start_time, m.start_time)
            end_overlap = min(own.end_time, m.end_time)
            matches.append({
                'username': m.username,
                'character': m.char_name,
                'day': m.day,
                'start': start_overlap,
                'end': end_overlap,
                'spec': m.spec,
                'keystone': m.keystone
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
        return "Ungültiges Zeitfenster."

    for day in days:
        overlapping = Entry.query.filter_by(
            user_id=session['user_id'],
            character_id=character_id,
            spec=spec,
            day=day
        ).filter(
            db.or_(
                db.and_(Entry.start_time <= start, Entry.end_time > start),
                db.and_(Entry.start_time < end, Entry.end_time >= end),
                db.and_(Entry.start_time >= start, Entry.end_time <= end)
            )
        ).first()

        if overlapping:
            overlapping.start_time = start
            overlapping.end_time = end
            overlapping.keystone = keystone
            overlapping.created_date = created_date
        else:
            new_entry = Entry(
                user_id=session['user_id'],
                character_id=character_id,
                day=day,
                start_time=start,
                end_time=end,
                spec=spec,
                keystone=keystone,
                created_date=created_date
            )
            db.session.add(new_entry)
    db.session.commit()
    return redirect('/')

@app.route('/delete_entry/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    if 'user_id' not in session:
        return redirect('/login')
    entry = Entry.query.get_or_404(entry_id)
    if entry.user_id == session['user_id']:
        db.session.delete(entry)
        db.session.commit()
    return redirect('/')

@app.route('/add_character', methods=['POST'])
def add_character():
    if 'user_id' not in session:
        return redirect('/login')
    char_name = request.form['char_name']
    new_char = Character(user_id=session['user_id'], char_name=char_name)
    db.session.add(new_char)
    db.session.commit()
    return redirect('/')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            return redirect('/')
        return "Login fehlgeschlagen."
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if User.query.filter_by(username=request.form['username']).first():
            return "Benutzername existiert bereits."
        hashed_pw = generate_password_hash(request.form['password'])
        new_user = User(username=request.form['username'], password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
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
    user = User.query.get(session['user_id'])
    db.session.delete(user)
    db.session.commit()
    session.clear()
    return redirect('/register')

if __name__ == '__main__':
    app.run(debug=True)
