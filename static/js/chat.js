document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    let currentRoom = 'General';
    
    // DOM Elements
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');
    const messagesDiv = document.getElementById('messages');
    const onlineUsersContainer = document.getElementById('online-users');
    const roomList = document.getElementById('roomList');
    const createRoomButton = document.getElementById('createRoomButton');

    // Connect to socket.io
    socket.on('connect', () => {
        console.log('Connected to server');
        // Join General room by default
        socket.emit('join', { room: 'General' });
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
        addRoom(data);
    });

    // Handle invite notifications
    socket.on('invited', (data) => {
        const fromUser = data.from;
        const roomName = data.room;
        const joinRoom = confirm(`${fromUser} invited you to join room "${roomName}". Do you want to join?`);
        if (joinRoom) {
            socket.emit('leave', { room: currentRoom });
            socket.emit('join', { room: roomName });
            currentRoom = roomName;
            
            // Update UI
            document.querySelectorAll('.room-item').forEach(item => {
                item.classList.remove('active');
            });
            const roomItem = document.querySelector(`[data-room="${roomName}"]`);
            if (roomItem) {
                roomItem.classList.add('active');
            }
            
            // Clear messages
            messagesDiv.innerHTML = '';
        }
    });

    // Fetch and display rooms periodically
    function fetchRooms() {
        fetch('/rooms')
            .then(response => response.json())
            .then(rooms => {
                roomList.innerHTML = '';  // Clear current list
                Object.entries(rooms).forEach(([name, info]) => {
                    addRoom({
                        room: name,
                        description: info.description,
                        category: info.category,
                        created_by: info.created_by,
                        users_count: info.users_count,
                        is_private: info.is_private
                    });
                });
            });
    }

    // Initial room fetch and setup refresh interval
    fetchRooms();
    setInterval(fetchRooms, 30000);  // Refresh every 30 seconds

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
        const description = document.getElementById('roomDescription').value.trim();
        const category = document.getElementById('roomCategory').value;
        const isPrivate = document.getElementById('roomPrivate').checked;

        if (roomName) {
            socket.emit('create_room', {
                room: roomName,
                description: description,
                category: category,
                is_private: isPrivate
            });
            const modal = bootstrap.Modal.getInstance(document.getElementById('createRoomModal'));
            modal.hide();
            
            // Clear form
            document.getElementById('newRoomName').value = '';
            document.getElementById('roomDescription').value = '';
            document.getElementById('roomCategory').value = 'Other';
            document.getElementById('roomPrivate').checked = false;
        }
    });

    // Handle room switching
    document.addEventListener('click', (e) => {
        const roomItem = e.target.closest('.room-item');
        if (roomItem && roomItem.dataset.room) {
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
        const currentUsername = window.currentUser?.username || '';
        div.className = `message ${data.username === currentUsername ? 'own' : 'other'}`;
        
        div.innerHTML = `
            <div class="bubble">
                ${data.username !== currentUsername ? `<strong>${data.username}</strong><br>` : ''}
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
        if (!onlineUsersContainer) return;
        onlineUsersContainer.innerHTML = '';
        users.forEach(user => {
            const div = document.createElement('div');
            div.className = 'd-flex justify-content-between align-items-center mb-2';
            div.dataset.userId = user.username;
            
            // Get current username from session
            const currentUsername = window.currentUser?.username || '';
            
            div.innerHTML = `
                <div>
                    <span class="user-status online"></span>
                    <span>${user.username}</span>
                </div>
                <div>
                    ${user.username !== currentUsername ? `<button class="btn btn-sm btn-outline-primary invite-btn" data-username="${user.username}">Invite</button>` : ''}
                </div>
            `;
            onlineUsersContainer.appendChild(div);
        });
        
        // Attach invite handlers
        onlineUsersContainer.querySelectorAll('.invite-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const toUser = btn.dataset.username;
                if (!currentRoom) {
                    alert('Please join a room first to send an invite.');
                    return;
                }
                socket.emit('invite', { to: toUser, room: currentRoom });
                alert(`Invite sent to ${toUser} to join ${currentRoom}`);
            });
        });
    }

    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    function addRoom(data) {
        const div = document.createElement('div');
        div.className = 'list-group-item room-item d-flex flex-column' + 
                       (data.room === 'General' ? ' active' : '');
        div.setAttribute('data-room', data.room);
        
        const roomHeader = document.createElement('div');
        roomHeader.className = 'd-flex justify-content-between align-items-center';
        
        const roomName = document.createElement('h6');
        roomName.className = 'mb-0';
        roomName.innerHTML = `${data.room} ${data.is_private ? '<i class="bi bi-lock-fill"></i>' : ''}`;
        
        const badge = document.createElement('span');
        badge.className = `badge bg-${data.category === 'General' ? 'primary' : 
                                    data.category === 'Gaming' ? 'success' :
                                    data.category === 'Technology' ? 'info' :
                                    data.category === 'Study' ? 'warning' : 'secondary'}`;
        badge.textContent = data.category;
        
        roomHeader.appendChild(roomName);
        roomHeader.appendChild(badge);
        div.appendChild(roomHeader);
        
        if (data.description) {
            const description = document.createElement('small');
            description.className = 'text-muted mt-1';
            description.textContent = data.description;
            div.appendChild(description);
        }
        
        const roomInfo = document.createElement('small');
        roomInfo.className = 'text-muted mt-1';
        roomInfo.innerHTML = `
            <i class="bi bi-people-fill"></i> ${data.users_count || 0} users
            ${data.created_by ? `• Created by ${data.created_by}` : ''}
        `;
        div.appendChild(roomInfo);
        
        // Add to the appropriate category section or create a new one
        let categorySection = document.querySelector(`#room-category-${data.category}`);
        if (!categorySection) {
            categorySection = document.createElement('div');
            categorySection.id = `room-category-${data.category}`;
            categorySection.className = 'room-category mb-3';
            
            const categoryHeader = document.createElement('h6');
            categoryHeader.className = 'category-header px-3 py-2 mb-2 bg-light';
            categoryHeader.textContent = data.category;
            
            categorySection.appendChild(categoryHeader);
            roomList.appendChild(categorySection);
        }
        
        categorySection.appendChild(div);
    }
});