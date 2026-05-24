from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)
DB_PATH = 'database.sqlite'

@app.route('/')
def index():
    return app.send_static_file('index.html')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/user/sync', methods=['POST'])
def sync_user():
    data = request.json
    telegram_id = data.get('id')
    if not telegram_id:
        return jsonify({"error": "Missing telegram_id"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (telegram_id, first_name, last_name, username, photo_url)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
        first_name=excluded.first_name,
        last_name=excluded.last_name,
        username=excluded.username,
        photo_url=excluded.photo_url
    ''', (telegram_id, data.get('firstName'), data.get('lastName'), data.get('username'), data.get('photoUrl')))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/video/rate', methods=['POST'])
def rate_video():
    data = request.json
    video_id = data.get('videoId')
    telegram_id = data.get('telegramId')
    rate_type = data.get('type') # 'like' or 'dislike'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if not rate_type: # Remove rating
        cursor.execute('DELETE FROM video_ratings WHERE video_id = ? AND telegram_id = ?', (video_id, telegram_id))
    else:
        cursor.execute('''
            INSERT INTO video_ratings (video_id, telegram_id, type)
            VALUES (?, ?, ?)
            ON CONFLICT(video_id, telegram_id) DO UPDATE SET type=excluded.type
        ''', (video_id, telegram_id, rate_type))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/video/ratings/<video_id>', methods=['GET'])
def get_ratings(video_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT type, COUNT(*) as count FROM video_ratings WHERE video_id = ? GROUP BY type', (video_id,))
    rows = cursor.fetchall()
    
    results = {"like": 0, "dislike": 0}
    for row in rows:
        results[row['type']] = row['count']
        
    # Get user's current rating if telegramId is provided
    user_rating = None
    telegram_id = request.args.get('telegramId')
    if telegram_id:
        cursor.execute('SELECT type FROM video_ratings WHERE video_id = ? AND telegram_id = ?', (video_id, telegram_id))
        row = cursor.fetchone()
        if row:
            user_rating = row['type']
            
    conn.close()
    return jsonify({**results, "userRating": user_rating})

@app.route('/api/video/save', methods=['POST'])
def save_video():
    data = request.json
    video_id = data.get('videoId')
    telegram_id = data.get('telegramId')
    action = data.get('action') # 'save' or 'unsave'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    if action == 'save':
        cursor.execute('INSERT OR IGNORE INTO saved_videos (video_id, telegram_id) VALUES (?, ?)', (video_id, telegram_id))
    else:
        cursor.execute('DELETE FROM saved_videos WHERE video_id = ? AND telegram_id = ?', (video_id, telegram_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/history/push', methods=['POST'])
def push_history():
    data = request.json
    video_id = data.get('videoId')
    telegram_id = data.get('telegramId')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO watch_history (video_id, telegram_id) VALUES (?, ?)', (video_id, telegram_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/search/history', methods=['POST', 'GET'])
def search_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        data = request.json
        telegram_id = data.get('telegramId')
        query = data.get('query')
        if query and telegram_id:
            cursor.execute('INSERT INTO search_history (telegram_id, query) VALUES (?, ?)', (telegram_id, query))
            conn.commit()
        return jsonify({"success": True})
    else:
        telegram_id = request.args.get('telegramId')
        cursor.execute('SELECT DISTINCT query FROM search_history WHERE telegram_id = ? ORDER BY created_at DESC LIMIT 10', (telegram_id,))
        rows = cursor.fetchall()
        conn.close()
        return jsonify([row['query'] for row in rows])

if __name__ == '__main__':
    app.run(port=5000)
