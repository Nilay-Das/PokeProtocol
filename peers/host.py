import socket
from protocol.messages import encode_message, decode_message

# Settings
HOST_IP = "127.0.0.1"
HOST_PORT = 5000
BUFFER = 4096

print("Starting the host...")

# Make a socket
# AF_INET means IPv4
# SOCK_DGRAM means UDP
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind((HOST_IP, HOST_PORT))

print("Host is ready and listening on " + HOST_IP + ":" + str(HOST_PORT))

while True:
    # Wait for a message
    data, address = s.recvfrom(BUFFER)
    
    # Turn bytes into string
    text = data.decode("utf-8")
    
    print("\nGot a message from:")
    print(address)
    print("Message content:")
    print(text)
    print("---")
    
    # Decode it
    message = decode_message(text)
    print("Decoded dictionary:")
    print(message)
    
    # Check if it is a handshake
    if message.get("message_type") == "HANDSHAKE_REQUEST":
        print("It is a handshake request!")
        
        # Make a reply
        reply = {
            "message_type": "HANDSHAKE_RESPONSE",
            "role": "HOST",
            "status": "OK"
        }
        
        # Encode it back to string
        reply_str = encode_message(reply)
        
        # Send it back
        s.sendto(reply_str.encode("utf-8"), address)
        print("Sent response back to joiner.")
