import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import emoji
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize extensions
socketio = SocketIO(app)
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    avatar = db.Column(db.String(200))
    status = db.Column(db.String(20), default='online')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='author', lazy=True)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='room', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    type = db.Column(db.String(20), default='text')  # text, image, file
    file_url = db.Column(db.String(200))
    edited = db.Column(db.Boolean, default=False)
    reactions = db.relationship('Reaction', backref='message', lazy=True)

class Reaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emoji = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email)
        user.password_hash = generate_password_hash(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('chat'))
        
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/chat')
@login_required
def chat():
    rooms = Room.query.all()
    return render_template('chat.html', rooms=rooms)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                current_user.avatar = filename
        
        current_user.status = request.form.get('status', current_user.status)
        db.session.commit()
        flash('Profile updated successfully')
        
    return render_template('profile.html')

# WebSocket events
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        current_user.status = 'online'
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        emit('user_status', {'user_id': current_user.id, 'status': 'online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        current_user.status = 'offline'
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        emit('user_status', {'user_id': current_user.id, 'status': 'offline'}, broadcast=True)

@socketio.on('join_room')
def handle_join_room(data):
    room = data.get('room')
    join_room(room)
    emit('status', {'msg': f'{current_user.username} has joined the room.'}, room=room)

@socketio.on('leave_room')
def handle_leave_room(data):
    room = data.get('room')
    leave_room(room)
    emit('status', {'msg': f'{current_user.username} has left the room.'}, room=room)

@socketio.on('message')
def handle_message(data):
    content = emoji.emojize(data.get('message'))
    room_id = data.get('room')
    msg_type = data.get('type', 'text')
    file_url = data.get('file_url')
    
    message = Message(
        content=content,
        user_id=current_user.id,
        room_id=room_id,
        type=msg_type,
        file_url=file_url
    )
    db.session.add(message)
    db.session.commit()
    
    emit('message', {
        'id': message.id,
        'content': content,
        'username': current_user.username,
        'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'type': msg_type,
        'file_url': file_url,
        'user_id': current_user.id
    }, room=room_id)

@socketio.on('reaction')
def handle_reaction(data):
    message_id = data.get('message_id')
    emoji_code = data.get('emoji')
    
    reaction = Reaction(
        emoji=emoji_code,
        user_id=current_user.id,
        message_id=message_id
    )
    db.session.add(reaction)
    db.session.commit()
    
    emit('reaction_update', {
        'message_id': message_id,
        'emoji': emoji_code,
        'user_id': current_user.id,
        'username': current_user.username
    }, broadcast=True)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'url': url_for('uploaded_file', filename=filename)})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Initialize database
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    socketio.run(app, debug=True)