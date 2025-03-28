from flask import Flask, render_template, request, redirect, flash, url_for
import psycopg2
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    return conn

# Ensure the players table exists
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        player_name = request.form.get('name', '').strip()
        action = request.form.get('action')

        if not player_name:
            flash('Name cannot be empty.', 'error')
            return redirect(url_for('index'))

        if action == 'register':
            try:
                cursor.execute('INSERT INTO players (name) VALUES (%s)', (player_name,))
                conn.commit()
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                flash(f'Player "{player_name}" is already registered.', 'error')
            else:
                cursor.execute('SELECT COUNT(*) FROM players')
                total_players = cursor.fetchone()[0]
                if total_players <= 18:
                    flash(f'Registration successful! {player_name} has secured a spot in the game.', 'success')
                else:
                    waiting_position = total_players - 18
                    flash(f'Registration successful! All spots are full, so {player_name} is on the waiting list (position {waiting_position}).', 'success')
            return redirect(url_for('index'))

        elif action == 'cancel':
            cursor.execute('DELETE FROM players WHERE name = %s', (player_name,))
            if cursor.rowcount == 0:
                flash(f'No active registration found for "{player_name}".', 'error')
            else:
                conn.commit()
                flash(f'Registration for "{player_name}" has been canceled.', 'success')
            return redirect(url_for('index'))

    cursor.execute('SELECT name FROM players ORDER BY id')
    all_players = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    main_players = all_players[:18]
    waiting_players = all_players[18:]

    courts = []
    for i in range(3):
        court_segment = main_players[i*6:(i+1)*6]
        side_a = court_segment[:3]
        side_b = court_segment[3:]
        courts.append({'side_a': side_a, 'side_b': side_b})

    return render_template('index.html', courts=courts, waiting_players=waiting_players)

if __name__ == '__main__':
    app.run(debug=True)
