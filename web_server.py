from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this in production
socketio = SocketIO(app)

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

@app.route('/')
def index():
    return render_template('index.html')

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
            'rooms': set(['General'])
        }
        join_room('General')
        emit('status', {
            'msg': f'🎉 {username} has joined the chat!',
            'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
        }, room='General')
        # Send user list update to all clients
        emit('update_users', {'users': list(users.values())}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in users:
        username = users[request.sid]['username']
        user_rooms = users[request.sid]['rooms'].copy()
        for room in user_rooms:
            leave_room(room)
            rooms[room]['users'].discard(username)
            emit('status', {
                'msg': f'⚠️ {username} has left the chat.',
                'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
            }, room=room)
        del users[request.sid]
        emit('update_users', {'users': list(users.values())}, broadcast=True)

@socketio.on('message')
def handle_message(data):
    username = users[request.sid]['username']
    room = data.get('room', 'General')
    message = data.get('message', '').strip()
    
    if message:
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        msg_data = {
            'username': username,
            'message': message,
            'timestamp': timestamp,
            'type': data.get('type', 'text')
        }
        rooms[room]['messages'].append(msg_data)
        emit('message', msg_data, room=room)

@socketio.on('join')
def on_join(data):
    username = users[request.sid]['username']
    room = data.get('room')
    
    if room and room in rooms:
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
    username = users[request.sid]['username']
    room = data.get('room')
    
    if room and room in rooms and room != 'General':
        leave_room(room)
        users[request.sid]['rooms'].discard(room)
        rooms[room]['users'].discard(username)
        emit('status', {
            'msg': f'👋 {username} has left {room}.',
            'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
        }, room=room)

@socketio.on('create_room')
def on_create_room(data):
    room_name = data.get('room')
    if room_name and room_name not in rooms:
        rooms[room_name] = {'users': set(), 'messages': []}
        emit('room_created', {'room': room_name}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)