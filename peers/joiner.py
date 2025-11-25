import socket
from protocol.messages import encode_message, decode_message
from protocol.reliability import ReliableChannel

# Settings
HOST_IP = "127.0.0.1"
HOST_PORT = 5000
BUFFER = 4096

print("Starting the joiner...")

# Make a socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Use our new reliable channel
channel = ReliableChannel(s)

# Prepare the handshake message
handshake = {
    "message_type": "HANDSHAKE_REQUEST",
    "role": "JOINER",
    "player_name": "TestJoiner"
}

print("Sending handshake reliably...")

# Send it with ACK
success = channel.send_with_ack(handshake, (HOST_IP, HOST_PORT))

if success:
    print("Handshake sent and ACK received!")
else:
    print("Could not send handshake reliably.")
    exit()

# Wait for a reply (HANDSHAKE_RESPONSE)
# Note: The response itself is not sent reliably in this simple version,
# we just wait for it.
print("Waiting for response from host...")
s.settimeout(5.0)

try:
    data, address = s.recvfrom(BUFFER)
    text = data.decode("utf-8")
    
    print("\nGot a response from host:")
    print(text)
    print("---")
    
    decoded = decode_message(text)
    print("Decoded response:")
    print(decoded)
    
except socket.timeout:
    print("Error: Host did not reply in time.")
