import socket
import threading
from queue import Queue
from protocol.messages import encode_message, decode_message
import time

class ReliableChannel:

    def __init__(self, sock, ack_queue: Queue):
        self.sock = sock
        self.ack_queue = ack_queue
        self.seq_num = 1
        self.ack_event = threading.Event()
        self.expected_ack = None

    # completely new send with ack function that implements a queue instead of recvfrom
    # this allows the host, joiner, and spectator peers to each implement their own
    # listener loops with unique logic
    def send_with_ack(self, message, addr, timeout=2.0):
        message["sequence_number"] = str(self.seq_num)
        encoded = encode_message(message)
        data = encoded.encode("utf-8")

        for attempt in range(3):
            print(f"Attempt {attempt + 1}: Sending seq={self.seq_num}")
            self.sock.sendto(data, addr)

            self.expected_ack = self.seq_num
            self.ack_event.clear()

            # Check queue for ACKs from listener
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    msg = self.ack_queue.get_nowait()
                    if msg.get("message_type") == "ACK" and int(msg.get("ack_number")) == self.expected_ack:
                        self.seq_num += 1
                        self.ack_event.set()
                        print("Ack received")
                        return True
                except:
                    continue

            print("Timed out waiting for ACK")
        print("Failed to send after 3 attempts")
        return False

    """   
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
    """