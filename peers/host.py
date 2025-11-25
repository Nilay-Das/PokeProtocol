import socket
from protocol.messages import encode_message, decode_message

# Settings
HOST_IP = "127.0.0.1"
HOST_PORT = 5000
BUFFER = 4096

print("Starting the host...")

# Make a socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind((HOST_IP, HOST_PORT))

print("Host is ready and listening on " + HOST_IP + ":" + str(HOST_PORT))

while True:
    # Wait for a message
    data, address = s.recvfrom(BUFFER)
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
    
    # 1. If it has a sequence number, we must send an ACK
    if "sequence_number" in message:
        # But we don't ACK an ACK!
        if message.get("message_type") != "ACK":
            seq = message["sequence_number"]
            print("It has sequence number " + seq + ", sending ACK...")
            
            ack_message = {
                "message_type": "ACK",
                "ack_number": seq
            }
            
            ack_str = encode_message(ack_message)
            s.sendto(ack_str.encode("utf-8"), address)
            print("Sent ACK back.")

    # 2. Handle Handshake
    if message.get("message_type") == "HANDSHAKE_REQUEST":
        print("It is a handshake request!")
        
        reply = {
            "message_type": "HANDSHAKE_RESPONSE",
            "role": "HOST",
            "status": "OK"
        }
        
        reply_str = encode_message(reply)
        s.sendto(reply_str.encode("utf-8"), address)
        print("Sent response back to joiner.")
