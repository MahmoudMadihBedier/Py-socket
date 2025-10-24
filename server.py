import socket
import threading
import logging
import json
import datetime
import argparse
import signal
import sys
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('chat_server.log'),
        logging.StreamHandler()
    ]
)

class ChatServer:
    def __init__(self, host="localhost", port=9090):
        self.host = host
        self.port = port
        self.server = None
        self.clients = {}  # {client_socket: {"username": str, "join_time": datetime, "msgs_sent": int}}
        self.rooms = defaultdict(set)  # {room_name: set(client_sockets)}
        self.commands = {
            "/help": self.cmd_help,
            "/msg": self.cmd_private_message,
            "/list": self.cmd_list_users,
            "/join": self.cmd_join_room,
            "/leave": self.cmd_leave_room,
            "/rooms": self.cmd_list_rooms,
            "/stats": self.cmd_show_stats
        }
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler('chat_server.log'),
                logging.StreamHandler()
            ]
        )


    def setup_server(self):
        """Initialize and setup the server socket"""
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Use an empty string for the host to bind to all available interfaces
            self.server.bind(("", self.port))
            self.server.listen(100)  # Support up to 100 pending connections
            logging.info(f"🔥 Chat server started on {self.host}:{self.port} 🔥")
            return True
        except Exception as e:
            logging.error(f"Failed to start server: {e}")
            return False

    def broadcast(self, message, sender=None, room=None):
        """Send message to all clients in a room or all clients if room is None"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        targets = self.rooms[room] if room else self.clients.keys()
        for client in targets:
            if client != sender:
                try:
                    client.send(formatted_message.encode())
                except:
                    self.remove_client(client)

    def handle_client_commands(self, client, message):
        """Handle special commands starting with /"""
        try:
            parts = message.split()
            command = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []

            if command in self.commands:
                self.commands[command](client, args)
                return True
            return False
        except Exception as e:
            self.send_to_client(client, f"Error executing command: {e}")
            return True

    def cmd_help(self, client, args):
        """Show available commands"""
        help_text = """
Available Commands:
/help - Show this help message
/msg <username> <message> - Send private message
/list - List all connected users
/join <room> - Join a chat room
/leave <room> - Leave a chat room
/rooms - List all active rooms
/stats - Show your chat statistics
        """
        self.send_to_client(client, help_text)

    def cmd_private_message(self, client, args):
        """Handle private messaging between users"""
        if len(args) < 2:
            self.send_to_client(client, "Usage: /msg <username> <message>")
            return

        target_username = args[0]
        message = " ".join(args[1:])
        sender_username = self.clients[client]["username"]

        for c, info in self.clients.items():
            if info["username"] == target_username:
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                self.send_to_client(c, f"[{timestamp}] 💌 Private from {sender_username}: {message}")
                self.send_to_client(client, f"[{timestamp}] 💌 Private to {target_username}: {message}")
                return

        self.send_to_client(client, f"⚠️ User {target_username} not found")

    def cmd_list_users(self, client, args):
        """List all connected users"""
        users = [f"{info['username']} (joined at {info['join_time'].strftime('%H:%M:%S')})"
                for info in self.clients.values()]
        self.send_to_client(client, "Connected users:\n" + "\n".join(users))

    def cmd_join_room(self, client, args):
        """Join a chat room"""
        if not args:
            self.send_to_client(client, "Usage: /join <room>")
            return
        
        room = args[0]
        self.rooms[room].add(client)
        username = self.clients[client]["username"]
        self.broadcast(f"👋 {username} joined the room!", sender=client, room=room)
        self.send_to_client(client, f"You joined room: {room}")

    def cmd_leave_room(self, client, args):
        """Leave a chat room"""
        if not args:
            self.send_to_client(client, "Usage: /leave <room>")
            return
        
        room = args[0]
        if room in self.rooms and client in self.rooms[room]:
            self.rooms[room].remove(client)
            username = self.clients[client]["username"]
            self.broadcast(f"👋 {username} left the room!", sender=client, room=room)
            self.send_to_client(client, f"You left room: {room}")
            
            # Clean up empty rooms
            if not self.rooms[room]:
                del self.rooms[room]

    def cmd_list_rooms(self, client, args):
        """List all active chat rooms"""
        if not self.rooms:
            self.send_to_client(client, "No active rooms")
            return
            
        room_info = []
        for room, members in self.rooms.items():
            users = [self.clients[c]["username"] for c in members]
            room_info.append(f"📁 {room} ({len(users)} users): {', '.join(users)}")
        self.send_to_client(client, "Active rooms:\n" + "\n".join(room_info))

    def cmd_show_stats(self, client, args):
        """Show user statistics"""
        if client in self.clients:
            info = self.clients[client]
            stats = f"""
Your Chat Statistics:
Username: {info['username']}
Connected since: {info['join_time'].strftime('%H:%M:%S')}
Messages sent: {info['msgs_sent']}
            """
            self.send_to_client(client, stats)

    def send_to_client(self, client, message):
        """Send a message to a specific client"""
        try:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            client.send(f"[{timestamp}] {message}\n".encode())
        except:
            self.remove_client(client)

    def handle_client(self, client):
        """Handle individual client connection"""
        try:
            # Get username
            self.send_to_client(client, "👤 Enter your username: ")
            username = client.recv(1024).decode().strip()
            
            # Check for duplicate username
            while any(info["username"] == username for info in self.clients.values()):
                self.send_to_client(client, "⚠️ Username already taken. Please choose another: ")
                username = client.recv(1024).decode().strip()
            
            # Store client info
            self.clients[client] = {
                "username": username,
                "join_time": datetime.datetime.now(),
                "msgs_sent": 0
            }
            
            # Welcome messages
            self.send_to_client(client, f"✅ Welcome {username}! Type /help for available commands.")
            self.broadcast(f"🎉 {username} joined the chat!\n", client)
            
            # Main message loop
            while True:
                message = client.recv(1024).decode().strip()
                if message:
                    if message.startswith('/'):
                        if not self.handle_client_commands(client, message):
                            self.send_to_client(client, "⚠️ Unknown command. Type /help for available commands.")
                    else:
                        self.clients[client]["msgs_sent"] += 1
                        username = self.clients[client]["username"]
                        self.broadcast(f"{username}: {message}\n", client)
        except:
            self.remove_client(client)

    def remove_client(self, client):
        """Remove a client and clean up their data"""
        if client in self.clients:
            username = self.clients[client]["username"]
            # Remove from all rooms
            for room in list(self.rooms.keys()):
                if client in self.rooms[room]:
                    self.rooms[room].remove(client)
                if not self.rooms[room]:
                    del self.rooms[room]
            
            # Remove client and notify others
            del self.clients[client]
            self.broadcast(f"⚠️ {username} left the chat.\n")
            client.close()
            logging.info(f"Client disconnected: {username}")

    def shutdown(self, sig=None, frame=None):
        """Gracefully shutdown the server"""
        logging.info("Shutting down server...")
        for client in list(self.clients.keys()):
            self.send_to_client(client, "⚠️ Server is shutting down...")
            self.remove_client(client)
        if self.server:
            self.server.close()
        logging.info("Server shutdown complete")
        sys.exit(0)

    def run(self):
        """Main server loop"""
        if not self.setup_server():
            return

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        while True:
            try:
                client, address = self.server.accept()
                logging.info(f"New connection from {address}")
                threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()
            except Exception as e:
                logging.error(f"Error accepting connection: {e}")


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Advanced Python Chat Server")
    parser.add_argument("--host", default="127.0.0.1run", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9090, help="Port to bind to")
    args = parser.parse_args()

    # Start server
    server = ChatServer(args.host, args.port)
    server.run()