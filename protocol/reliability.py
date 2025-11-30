import socket
from protocol.messages import encode_message, decode_message

class ReliableChannel:
    def __init__(self, sock):
        self.sock = sock
        self.seq_num = 1
        
    def send_with_ack(self, message, address):
        # Add the sequence number
        message["sequence_number"] = str(self.seq_num)
        
        # Prepare to send
        encoded = encode_message(message)
        data = encoded.encode("utf-8")
        
        # Try 3 times
        for i in range(3):
            print("Attempt " + str(i + 1) + ": Sending message with seq=" + str(self.seq_num))
            self.sock.sendto(data, address)
            
            # Wait for ACK
            self.sock.settimeout(3.0)
            
            try:
                # Listen for response
                response_data, addr = self.sock.recvfrom(4096)
                response_text = response_data.decode("utf-8")
                
                # Decode it
                response_msg = decode_message(response_text)
                
                # Check if it is an ACK
                if response_msg.get("message_type") == "ACK":
                    print(f"Expected ack {self.seq_num}") #debugging
                    if response_msg.get("ack_number") == str(self.seq_num):
                        print("Got the ACK! Message delivered.")
                        self.seq_num = self.seq_num + 1
                        self.sock.settimeout(None)
                        return True
                    else:
                        print("Got an ACK but for the wrong number.")
                else:
                    print("Got a message but it was not an ACK.")
                    print(f"Received message: \n{response_msg}") #debugging
                    
            except socket.timeout:
                print("Timed out waiting for ACK.")
                
        # If we get here, we failed
        print("Failed to send message after 3 tries.")
        self.sock.settimeout(None)
        return False
