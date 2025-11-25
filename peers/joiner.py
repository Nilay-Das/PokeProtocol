import socket
from protocol.messages import encode_message, decode_message

# Settings
HOST_IP = "127.0.0.1"
HOST_PORT = 5000
BUFFER = 4096

print("Starting the joiner...")

# Make a socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Prepare the handshake message
handshake = {
    "message_type": "HANDSHAKE_REQUEST",
    "role": "JOINER",
    "player_name": "TestJoiner"
}

print("Encoding handshake message...")
encoded_handshake = encode_message(handshake)

# Send it to the host
print("Sending to host at " + HOST_IP + ":" + str(HOST_PORT))
s.sendto(encoded_handshake.encode("utf-8"), (HOST_IP, HOST_PORT))

# Wait for a reply
print("Waiting for response...")
s.settimeout(5.0) # Wait for 5 seconds max

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
