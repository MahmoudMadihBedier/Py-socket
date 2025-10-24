document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    let currentRoom = 'General';
    
    // DOM Elements
    const messageForm = document.getElementById('messageForm');
    const messageInput = document.getElementById('messageInput');
    const messagesDiv = document.getElementById('messages');
    const userList = document.getElementById('userList');
    const roomList = document.getElementById('roomList');
    const createRoomButton = document.getElementById('createRoomButton');

    // Connect to socket.io
    socket.on('connect', () => {
        console.log('Connected to server');
    });

    // Handle incoming messages
    socket.on('message', (data) => {
        appendMessage(data);
    });

    // Handle status messages
    socket.on('status', (data) => {
        appendStatusMessage(data.msg);
    });

    // Handle user list updates
    socket.on('update_users', (data) => {
        updateUserList(data.users);
    });

    // Handle new room creation
    socket.on('room_created', (data) => {
        addRoom(data.room);
    });

    // Send message
    messageForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (message) {
            socket.emit('message', {
                message: message,
                room: currentRoom
            });
            messageInput.value = '';
        }
    });

    // Create new room
    createRoomButton.addEventListener('click', () => {
        const roomName = document.getElementById('newRoomName').value.trim();
        if (roomName) {
            socket.emit('create_room', { room: roomName });
            const modal = bootstrap.Modal.getInstance(document.getElementById('createRoomModal'));
            modal.hide();
            document.getElementById('newRoomName').value = '';
        }
    });

    // Handle room switching
    roomList.addEventListener('click', (e) => {
        const roomItem = e.target.closest('.room-item');
        if (roomItem) {
            const newRoom = roomItem.dataset.room;
            if (newRoom !== currentRoom) {
                socket.emit('leave', { room: currentRoom });
                socket.emit('join', { room: newRoom });
                currentRoom = newRoom;
                
                // Update UI
                document.querySelectorAll('.room-item').forEach(item => {
                    item.classList.remove('active');
                });
                roomItem.classList.add('active');
                
                // Clear messages
                messagesDiv.innerHTML = '';
            }
        }
    });

    // Helper functions
    function appendMessage(data) {
        const div = document.createElement('div');
        div.className = `message ${data.username === username ? 'own' : 'other'}`;
        
        div.innerHTML = `
            <div class="bubble">
                ${data.username !== username ? `<strong>${data.username}</strong><br>` : ''}
                ${data.message}
            </div>
            <div class="info">${data.timestamp}</div>
        `;
        
        messagesDiv.appendChild(div);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    function appendStatusMessage(message) {
        const div = document.createElement('div');
        div.className = 'status-message';
        div.textContent = message;
        messagesDiv.appendChild(div);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    function updateUserList(users) {
        userList.innerHTML = '';
        users.forEach(user => {
            const div = document.createElement('div');
            div.className = 'user-item';
            div.innerHTML = `
                <span class="user-status online"></span>
                ${user.username}
            `;
            userList.appendChild(div);
        });
    }

    function addRoom(roomName) {
        const div = document.createElement('div');
        div.className = 'room-item';
        div.dataset.room = roomName;
        div.innerHTML = `<i class="fas fa-hashtag"></i> ${roomName}`;
        roomList.appendChild(div);
    }
});