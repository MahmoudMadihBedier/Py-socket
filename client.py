import socket
import threading
import argparse
import sys
import signal
import datetime
from queue import Queue
import os

class ChatClient:
    def __init__(self, host="127.0.0.1", port=9090):
        self.host = host
        self.port = port
        self.client = None
        self.username = None
        self.connected = False
        self.message_queue = Queue()
        self.command_descriptions = {
            "/help": "Show this help message",
            "/msg": "Send private message: /msg <username> <message>",
            "/list": "List all connected users",
            "/join": "Join a chat room: /join <room>",
            "/leave": "Leave a chat room: /leave <room>",
            "/rooms": "List all active rooms",
            "/stats": "Show your chat statistics",
            "/clear": "Clear the screen",
            "/quit": "Exit the chat application"
        }

    def connect(self):
        """Connect to the chat server"""
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((self.host, self.port))
            self.connected = True
            return True
        except Exception as e:
            print(f"⚠️ Failed to connect to server: {e}")
            return False

    def display_welcome(self):
        """Display welcome message and instructions"""
        print("""
╔══════════════════════════════════════╗
║         Welcome to PyChat!           ║
║                                      ║
║  Type your messages and press Enter  ║
║  Type /help to see available commands║
║  Press Ctrl+C to exit               ║
╚══════════════════════════════════════╝
""")

    def handle_user_input(self):
        """Handle user input in a separate thread"""
        while self.connected:
            try:
                message = input()
                if message.lower() == "/quit":
                    self.shutdown()
                    break
                elif message.lower() == "/clear":
                    os.system('clear' if os.name == 'posix' else 'cls')
                    self.display_welcome()
                else:
                    self.client.send(message.encode())
            except (EOFError, KeyboardInterrupt):
                self.shutdown()
                break
            except Exception as e:
                print(f"⚠️ Error sending message: {e}")
                break

    def receive_messages(self):
        """Receive and display messages from the server"""
        while self.connected:
            try:
                message = self.client.recv(1024).decode()
                if not message:
                    break
                
                # Handle username prompt
                if message.strip() == "👤 Enter your username: ":
                    print(message, end='')
                    continue
                
                # Clear line and print message
                print(f"\r{message}", end='')
                
                # Reprint the input prompt
                print("> ", end='', flush=True)
                
            except Exception as e:
                print(f"\n⚠️ Lost connection to server: {e}")
                self.connected = False
                break

    def shutdown(self, sig=None, frame=None):
        """Gracefully shutdown the client"""
        print("\n👋 Goodbye!")
        self.connected = False
        if self.client:
            self.client.close()
        sys.exit(0)

    def run(self):
        """Main client loop"""
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.shutdown)
        
        if not self.connect():
            return

        self.display_welcome()

        # Start message receiving thread
        receive_thread = threading.Thread(target=self.receive_messages)
        receive_thread.daemon = True
        receive_thread.start()

        # Start user input thread
        input_thread = threading.Thread(target=self.handle_user_input)
        input_thread.daemon = True
        input_thread.start()

        # Keep main thread alive
        try:
            input_thread.join()
        except KeyboardInterrupt:
            self.shutdown()


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Python Chat Client")
    parser.add_argument("--host", default="127.0.0.1", help="Server host address")
    parser.add_argument("--port", type=int, default=9090, help="Server port")
    args = parser.parse_args()

    # Start client
    client = ChatClient(args.host, args.port)
    client.run()