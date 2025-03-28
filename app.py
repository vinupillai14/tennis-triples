from flask import Flask, render_template, request, redirect, flash, url_for
import psycopg2
import os
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    return psycopg2.connect(os.getenv('DATABASE_URL'))

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cancellations (
            id SERIAL PRIMARY KEY,
            name TEXT,
            cancelled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_assignments (
            name TEXT PRIMARY KEY,
            team_number INTEGER
        );
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
                cursor.execute('INSERT INTO team_assignments (name, team_number) VALUES (%s, NULL)', (player_name,))
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
            cursor.execute('DELETE FROM players WHERE name = %s RETURNING name', (player_name,))
            deleted = cursor.fetchone()
            if deleted:
                cursor.execute('INSERT INTO cancellations (name) VALUES (%s)', (player_name,))
                cursor.execute('DELETE FROM team_assignments WHERE name = %s', (player_name,))
                conn.commit()
                flash(f'Registration for "{player_name}" has been canceled.', 'success')
            else:
                flash(f'No active registration found for "{player_name}".', 'error')
            return redirect(url_for('index'))

    cursor.execute('SELECT name FROM players ORDER BY id')
    all_players = [row[0] for row in cursor.fetchall()]
    cursor.execute('SELECT name, team_number FROM team_assignments')
    assignments = dict(cursor.fetchall())
    cursor.execute('SELECT name, cancelled_at FROM cancellations ORDER BY cancelled_at DESC LIMIT 20')
    cancellations = cursor.fetchall()

    assigned_players = [name for name in all_players if assignments.get(name)]
    main_players = assigned_players[:18]
    waiting_players = all_players[18:]

    # promoted player logic
    cursor.execute('SELECT name, id FROM players ORDER BY id')
    joined_order = {row[0].strip().lower(): row[1] for row in cursor.fetchall()}
    cancel_ids = [c[0] for c in cancellations]
    promoted_players = []
    if cancel_ids:
        cursor.execute('SELECT MIN(id) FROM players WHERE name IN %s', (tuple(cancel_ids),))
        min_cancel_id = cursor.fetchone()[0]
        print('Cancel ID threshold:', min_cancel_id)
        if min_cancel_id:
            for name in main_players:
                if joined_order.get(name.strip().lower(), 0) > min_cancel_id:
                    promoted_players.append(name)

    cursor.close()
    return render_template(
        'index.html',
        teams=[main_players[i*3:(i+1)*3] for i in range(6)],
        waiting_players=waiting_players,
        all_players=all_players,
        cancellations=cancellations,
        promoted_players=promoted_players
    )

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    key = request.args.get('key')
    if key != os.getenv('ADMIN_KEY', 'admin123'):
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        data = request.form.get('assignments')
        if data:
            try:
                assignments = json.loads(data)
                for name, team in assignments.items():
                    print(f"Assigning {name} to team {team}")
                    if team is None:
                        cursor.execute('''
                            INSERT INTO team_assignments (name, team_number)
                            VALUES (%s, NULL)
                            ON CONFLICT (name)
                            DO UPDATE SET team_number = NULL
                        ''', (name,))
                    else:
                        cursor.execute('''
                            INSERT INTO team_assignments (name, team_number)
                            VALUES (%s, %s)
                            ON CONFLICT (name)
                            DO UPDATE SET team_number = EXCLUDED.team_number
                        ''', (name, int(team)))
                conn.commit()
                flash('Team assignments updated.', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error updating assignments: {str(e)}', 'error')

    cursor.execute('SELECT name FROM players ORDER BY id')
    players = [row[0] for row in cursor.fetchall()]
    cursor.execute('SELECT name, team_number FROM team_assignments')
    assignments = dict(cursor.fetchall())
    cursor.execute('SELECT COUNT(*) FROM players')
    total_players = cursor.fetchone()[0]
    cursor.execute('SELECT name, cancelled_at FROM cancellations ORDER BY cancelled_at DESC LIMIT 20')
    cancellations = cursor.fetchall()

    cursor.close()
    return render_template(
        'admin.html',
        total_players=total_players,
        cancellations=cancellations,
        assignments=assignments,
        players=players
    )

@app.route('/reset', methods=['POST'])
def reset():
    key = request.args.get('key')
    if key != os.getenv('ADMIN_KEY', 'admin123'):
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM players')
    cursor.execute('DELETE FROM cancellations')
    cursor.execute('DELETE FROM team_assignments')
    conn.commit()
    cursor.close()
    conn.close()

    flash('All player data has been reset.', 'success')
    return redirect(url_for('admin', key=key))

if __name__ == '__main__':
    app.run(debug=True)
