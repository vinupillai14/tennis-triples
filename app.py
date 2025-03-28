from flask import Flask, render_template, request, redirect, flash, url_for
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flash messages (use a secure random key in production)

# Initialize SQLite database (create table if it doesn't exist)
conn = sqlite3.connect('tennis.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS players (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
)
''')
conn.commit()
conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    # Open a new database connection for this request
    conn = sqlite3.connect('tennis.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        player_name = request.form.get('name', '').strip()  # Player's name from form, trimmed
        action = request.form.get('action')                # Action: "register" or "cancel"

        if not player_name:
            flash('Name cannot be empty.', 'error')
            return redirect(url_for('index'))

        if action == 'register':
            try:
                # Insert the new player (will fail if name already exists due to UNIQUE constraint)
                cursor.execute('INSERT INTO players (name) VALUES (?)', (player_name,))
                conn.commit()
            except sqlite3.IntegrityError:
                # Name already registered (UNIQUE constraint violated)
                flash(f'Player "{player_name}" is already registered.', 'error')
            else:
                # Check how many players are now registered to determine if on main list or waiting list
                cursor.execute('SELECT COUNT(*) FROM players')
                total_players = cursor.fetchone()[0]
                if total_players <= 18:
                    # Within first 18 players -> secured a main spot
                    flash(f'Registration successful! {player_name} has secured a spot in the game.', 'success')
                else:
                    # Beyond 18 players -> added to waiting list
                    waiting_position = total_players - 18
                    flash(f'Registration successful! All spots are full, so {player_name} is on the waiting list (position {waiting_position}).', 'success')
            return redirect(url_for('index'))

        elif action == 'cancel':
            # Remove the player from the registration list (if present)
            cursor.execute('DELETE FROM players WHERE name = ?', (player_name,))
            if cursor.rowcount == 0:
                # No matching name found in current registrations
                flash(f'No active registration found for "{player_name}".', 'error')
            else:
                conn.commit()
                flash(f'Registration for "{player_name}" has been canceled.', 'success')
            return redirect(url_for('index'))

    # For GET requests (or after a POST redirect), retrieve current allocations
    cursor.execute('SELECT name FROM players ORDER BY id')
    all_players = [row[0] for row in cursor.fetchall()]  # List of all registered player names in sign-up order

    # Split into main players (first 18) and waiting list (rest)
    main_players = all_players[:18]
    waiting_players = all_players[18:]

    # Group main players into courts (3 courts, 6 players each, split into 3-per side)
    courts = []  
    for i in range(3):
        # Determine players for court i (indices 0-5 for Court 1, 6-11 for Court 2, 12-17 for Court 3)
        court_segment = main_players[i*6:(i+1)*6]
        side_a = court_segment[:3]
        side_b = court_segment[3:]
        courts.append({'side_a': side_a, 'side_b': side_b})

    conn.close()
    # Render the template with court allocations and waiting list
    return render_template('index.html', courts=courts, waiting_players=waiting_players)

# (Optional) Run the app if executed directly
if __name__ == '__main__':
    app.run(debug=True)

