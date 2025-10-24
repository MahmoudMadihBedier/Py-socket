import socket
import threading

# Server address (change IP if connecting from another device)
HOST = "127.0.0.1"
PORT = 9090

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))


# Receive messages from the server
def receive_messages():
    while True:
        try:
            message = client.recv(1024).decode()
            if message:
                print(message)
            else:
                break
        except:
            print("⚠️ Connection lost!")
            client.close()
            break


# Send messages to the server
def send_messages():
    while True:
        msg = input("")
        client.send(msg.encode())


receive_thread = threading.Thread(target=receive_messages)
receive_thread.start()

send_thread = threading.Thread(target=send_messages)
send_thread.start()