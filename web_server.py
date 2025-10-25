from flask import Flask, render_template, request, session, redirect, url_for, jsonify, send_from_directory, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
import os
import datetime
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this in production
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
socketio = SocketIO(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Store connected users and their rooms
users = {}
rooms = {
    'General': {
        'users': set(),
        'messages': [],
        'description': 'Main chat room for everyone',
        'created_by': 'System',
        'created_at': datetime.datetime.now(),
        'category': 'General',
        'is_private': False
    }
}

# Track user data
user_data = {}
# Activity log (in-memory)
activity_log = []

def log_activity(event_type, description, meta=None):
    entry = {
        'id': uuid.uuid4().hex,
        'event': event_type,
        'description': description,
        'meta': meta or {},
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    activity_log.append(entry)
    # keep the log bounded
    if len(activity_log) > 1000:
        del activity_log[0]
    # broadcast to all clients
    try:
        socketio.emit('activity', entry, broadcast=True)
    except Exception:
        pass

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        if username:
            session['username'] = username
            return redirect(url_for('chat'))
    return render_template('index.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/rooms')
def get_rooms():
    public_rooms = {
        name: {
            'description': info['description'],
            'users_count': len(info['users']),
            'category': info.get('category', 'Other'),
            'created_by': info['created_by'],
            'created_at': info['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
            'is_private': info.get('is_private', False)
        }
        for name, info in rooms.items()
        if not info.get('is_private', False)
    }
    return jsonify(public_rooms)


@app.route('/create_room', methods=['POST'])
def create_room():
    data = request.get_json() or {}
    name = data.get('name') or data.get('room')
    description = data.get('description', '')
    category = data.get('category', 'Other')
    is_private = data.get('is_private', False)
    if name and name not in rooms:
        created_by = session.get('username', 'System')
        rooms[name] = {
            'users': set(),
            'messages': [],
            'description': description,
            'created_by': created_by,
            'created_at': datetime.datetime.now(),
            'category': category,
            'is_private': is_private
        }
    # log activity
    log_activity('create_room', f"Room '{name}' created", {'room': name, 'created_by': created_by})
    return jsonify({'ok': True}), 201
    return jsonify({'ok': False, 'error': 'Room exists or invalid name'}), 400


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    url = url_for('uploaded_file', filename=filename)
    # log activity
    user = session.get('username', 'Anonymous')
    log_activity('upload', f'File uploaded by {user}: {filename}', {'filename': filename, 'user': user})
    return jsonify({'url': url})


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        username = request.form.get('username')
        if username:
            session['username'] = username
            return render_template('chat.html', username=username, rooms=rooms)
    return redirect(url_for('index'))

@socketio.on('connect')
def handle_connect():
    username = session.get('username')
    if username:
        users[request.sid] = {
            'username': username,
            'rooms': set(['General']),
            'sid': request.sid,
            'avatar': '/static/img/default_avatar.svg',
            'connected_at': datetime.datetime.now().isoformat()
        }
        # Add to General room users set
        rooms['General']['users'].add(username)
        join_room('General')
        emit('status', {
            'msg': f'🎉 {username} has joined the chat!',
            'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
        }, room='General')
        # Send user list update to all clients
        emit('update_users', {'users': list(users.values())}, broadcast=True)
        # send recent activity log to this client
        try:
            emit('activity_log', {'logs': activity_log}, room=request.sid)
        except Exception:
            pass
        # record activity
        log_activity('connect', f'{username} connected', {'username': username})

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in users:
        username = users[request.sid]['username']
        user_rooms = users[request.sid]['rooms'].copy()
        for room in user_rooms:
            leave_room(room)
            if room in rooms:
                rooms[room]['users'].discard(username)
            emit('status', {
                'msg': f'⚠️ {username} has left the chat.',
                'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
            }, room=room)
        del users[request.sid]
        emit('update_users', {'users': list(users.values())}, broadcast=True)
    # log disconnect
    log_activity('disconnect', f'{username} disconnected', {'username': username})

@socketio.on('message')
def handle_message(data):
    username = users.get(request.sid, {}).get('username', 'Unknown')
    room = data.get('room', 'General')
    message = data.get('message', '').strip()
    msg_type = data.get('type', 'text')
    file_url = data.get('file_url')

    if message or file_url:
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        msg_data = {
            'id': uuid.uuid4().hex,
            'user_id': username,
            'username': username,
            'content': message,
            'timestamp': timestamp,
            'type': msg_type,
            'file_url': file_url,
            'edited': False
        }
        # Ensure room exists
        if room not in rooms:
            rooms[room] = {'users': set(), 'messages': [], 'description': '', 'created_by': 'System', 'created_at': datetime.datetime.now(), 'category': 'Other', 'is_private': False}
    rooms[room]['messages'].append(msg_data)
    emit('message', msg_data, room=room)
    # log activity
    log_activity('message', f"{username} sent a message in {room}", {'room': room, 'username': username, 'message': message[:200]})

@socketio.on('join')
def on_join(data):
    username = users.get(request.sid, {}).get('username')
    room = data.get('room')
    if not room or not username:
        return
    if room not in rooms:
        # create room if missing
        rooms[room] = {'users': set(), 'messages': [], 'description': '', 'created_by': username, 'created_at': datetime.datetime.now(), 'category': 'Other', 'is_private': False}
    join_room(room)
    users[request.sid]['rooms'].add(room)
    rooms[room]['users'].add(username)
    emit('status', {
        'msg': f'👋 {username} has joined {room}!',
        'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
    }, room=room)
    # Send room history
    for msg in rooms[room]['messages'][-50:]:  # Last 50 messages
        emit('message', msg)

@socketio.on('leave')
def on_leave(data):
    username = users.get(request.sid, {}).get('username')
    room = data.get('room')
    if not room or not username:
        return
    if room in rooms and room != 'General':
        leave_room(room)
        users[request.sid]['rooms'].discard(room)
        rooms[room]['users'].discard(username)
        emit('status', {
            'msg': f'👋 {username} has left {room}.',
            'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
        }, room=room)

@socketio.on('leave_room')
def on_leave_room(data):
    # alias to keep compatibility with client naming
    on_leave(data)

@socketio.on('join_room')
def on_join_room(data):
    on_join(data)

@socketio.on('typing')
def on_typing(data):
    room = data.get('room')
    typing = data.get('typing', False)
    username = users.get(request.sid, {}).get('username')
    emit('typing_status', {'room': room, 'typing': typing, 'username': username, 'user_id': username}, room=room)

@socketio.on('delete_message')
def on_delete_message(data):
    room = data.get('room')
    message_id = data.get('message_id')
    # Remove from server store if present
    if room in rooms:
        rooms[room]['messages'] = [m for m in rooms[room]['messages'] if m.get('id') != message_id]
    emit('delete_message', {'message_id': message_id}, room=room)

@socketio.on('invite')
def on_invite(data):
    target = data.get('to')
    room = data.get('room')
    from_user = users.get(request.sid, {}).get('username')
    # find the sid(s) for target username
    for sid, u in users.items():
        if u.get('username') == target:
            emit('invited', {'from': from_user, 'room': room}, room=sid)
            # log activity
            log_activity('invite', f'{from_user} invited {target} to {room}', {'from': from_user, 'to': target, 'room': room})
            break


@app.route('/activity')
def get_activity():
    # return recent activity logs
    return jsonify({'logs': activity_log})

@socketio.on('create_room')
def on_create_room(data):
    room_name = data.get('room')
    description = data.get('description', '')
    category = data.get('category', 'Other')
    is_private = data.get('is_private', False)
    
    if room_name and room_name not in rooms:
        username = users[request.sid]['username']
        rooms[room_name] = {
            'users': set(),
            'messages': [],
            'description': description,
            'created_by': username,
            'created_at': datetime.datetime.now(),
            'category': category,
            'is_private': is_private
        }
        emit('room_created', {
            'room': room_name,
            'description': description,
            'category': category,
            'created_by': username,
            'is_private': is_private
        }, broadcast=True)
        log_activity('create_room', f"Room '{room_name}' created by {username}", {'room': room_name, 'created_by': username})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)