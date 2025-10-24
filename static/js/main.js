document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    let currentRoom = null;
    let typingTimeout = null;

    // Connect to socket.io
    socket.on('connect', () => {
        console.log('Connected to server');
    });

    // Handle incoming messages
    socket.on('message', data => {
        const messageList = document.getElementById('messages');
        const isOwn = data.user_id === currentUser.id;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isOwn ? 'own' : 'other'}`;
        messageDiv.dataset.messageId = data.id;

        let content = '';
        if (data.type === 'text') {
            content = data.content;
        } else if (data.type === 'image') {
            content = `<img src="${data.file_url}" class="img-fluid" alt="Shared image">`;
        } else if (data.type === 'file') {
            content = `<a href="${data.file_url}" target="_blank">
                        <i class="fas fa-file"></i> Download File
                      </a>`;
        }

        messageDiv.innerHTML = `
            <div class="message-bubble">
                ${!isOwn ? `<strong>${data.username}</strong><br>` : ''}
                ${content}
            </div>
            <div class="message-info">
                ${data.timestamp}
                ${data.edited ? ' (edited)' : ''}
            </div>
            <div class="message-actions">
                <button class="btn btn-sm btn-link react-btn">
                    <i class="far fa-smile"></i>
                </button>
                ${isOwn ? `
                    <button class="btn btn-sm btn-link edit-btn">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-link delete-btn">
                        <i class="fas fa-trash"></i>
                    </button>
                ` : ''}
            </div>
            <div class="reaction-list"></div>
        `;

        messageList.appendChild(messageDiv);
        messageList.scrollTop = messageList.scrollHeight;
    });

    // Handle user status updates
    socket.on('user_status', data => {
        const userElement = document.querySelector(`[data-user-id="${data.user_id}"]`);
        if (userElement) {
            const statusDot = userElement.querySelector('.user-status');
            statusDot.className = `user-status ${data.status}`;
        }
    });

    // Handle reactions
    socket.on('reaction_update', data => {
        const messageElement = document.querySelector(`[data-message-id="${data.message_id}"]`);
        if (messageElement) {
            const reactionList = messageElement.querySelector('.reaction-list');
            const reaction = document.createElement('span');
            reaction.className = 'reaction';
            reaction.innerHTML = `${data.emoji} <small>${data.username}</small>`;
            reactionList.appendChild(reaction);
        }
    });

    // Join room
    document.querySelectorAll('.room-item').forEach(room => {
        room.addEventListener('click', () => {
            const roomId = room.dataset.roomId;
            if (currentRoom) {
                socket.emit('leave_room', { room: currentRoom });
            }
            currentRoom = roomId;
            socket.emit('join_room', { room: roomId });
            
            // Clear messages
            document.getElementById('messages').innerHTML = '';
            
            // Update active room UI
            document.querySelectorAll('.room-item').forEach(r => r.classList.remove('active'));
            room.classList.add('active');
        });
    });

    // Send message
    const messageForm = document.getElementById('message-form');
    messageForm.addEventListener('submit', e => {
        e.preventDefault();
        if (!currentRoom) return;

        const input = document.getElementById('message-input');
        const message = input.value.trim();
        
        if (message) {
            socket.emit('message', {
                message: message,
                room: currentRoom,
                type: 'text'
            });
            input.value = '';
        }
    });

    // File upload
    const fileButton = document.getElementById('file-button');
    const fileInput = document.getElementById('file-input');

    fileButton.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', async () => {
        const file = fileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (data.url) {
                socket.emit('message', {
                    message: file.name,
                    room: currentRoom,
                    type: file.type.startsWith('image/') ? 'image' : 'file',
                    file_url: data.url
                });
            }
        } catch (error) {
            console.error('Error uploading file:', error);
        }

        fileInput.value = '';
    });

    // Typing indicator
    const messageInput = document.getElementById('message-input');
    messageInput.addEventListener('input', () => {
        if (!currentRoom) return;

        if (typingTimeout) clearTimeout(typingTimeout);

        socket.emit('typing', { room: currentRoom, typing: true });

        typingTimeout = setTimeout(() => {
            socket.emit('typing', { room: currentRoom, typing: false });
        }, 1000);
    });

    socket.on('typing_status', data => {
        const indicator = document.getElementById('typing-indicator');
        if (data.typing && data.user_id !== currentUser.id) {
            indicator.textContent = `${data.username} is typing...`;
        } else {
            indicator.textContent = '';
        }
    });

    // Create room
    const createRoomForm = document.getElementById('create-room-form');
    document.getElementById('create-room-button').addEventListener('click', async () => {
        const name = document.getElementById('room-name').value.trim();
        const description = document.getElementById('room-description').value.trim();

        if (name) {
            try {
                const response = await fetch('/create_room', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ name, description })
                });

                if (response.ok) {
                    location.reload();
                }
            } catch (error) {
                console.error('Error creating room:', error);
            }
        }
    });

    // Message actions (edit, delete, react)
    document.getElementById('messages').addEventListener('click', e => {
        const messageElement = e.target.closest('.message');
        if (!messageElement) return;

        if (e.target.closest('.react-btn')) {
            picker.togglePicker(e.target.closest('.react-btn'));
        }

        if (e.target.closest('.edit-btn')) {
            const content = messageElement.querySelector('.message-bubble').textContent.trim();
            messageInput.value = content;
            messageInput.focus();
            messageInput.dataset.editMessageId = messageElement.dataset.messageId;
        }

        if (e.target.closest('.delete-btn')) {
            if (confirm('Are you sure you want to delete this message?')) {
                socket.emit('delete_message', {
                    message_id: messageElement.dataset.messageId,
                    room: currentRoom
                });
            }
        }
    });
});