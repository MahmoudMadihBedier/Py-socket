import socket
import threading

# Server setup
HOST = "192.168.1"   # Listen on all interfaces
PORT = 9090        # Port for chat

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()

print(f"🔥 Chat server started on {HOST}:{PORT} 🔥")

clients = []   # Store connected client sockets
usernames = [] # Store usernames


# Send message to all connected clients
def broadcast(message, sender_socket=None):
    for client in clients:
        if client != sender_socket:
            try:
                client.send(message)
            except:
                remove_client(client)


# Handle messages from one client
def handle_client(client):
    while True:
        try:
            message = client.recv(1024)
            broadcast(message, client)
        except:
            remove_client(client)
            break


# Remove a client when they disconnect
def remove_client(client):
    if client in clients:
        index = clients.index(client)
        username = usernames[index]
        clients.remove(client)
        usernames.remove(username)
        broadcast(f"⚠️ {username} left the chat.\n".encode())
        client.close()


# Accept incoming connections
def receive_connections():
    while True:
        client, address = server.accept()
        print(f"✅ Connected with {str(address)}")

        client.send("Enter your username: ".encode())
        username = client.recv(1024).decode().strip()

        usernames.append(username)
        clients.append(client)

        print(f"👤 Username is {username}")
        broadcast(f"🎉 {username} joined the chat!\n".encode(), client)
        client.send("✅ You are now connected to the chat server.\n".encode())

        thread = threading.Thread(target=handle_client, args=(client,))
        thread.start()


receive_connections()