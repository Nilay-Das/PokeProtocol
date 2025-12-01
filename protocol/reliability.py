import socket
import threading
from queue import Queue, Empty
from protocol.messages import encode_message, decode_message
import time

class ReliableChannel:

    def __init__(self, sock, ack_queue: Queue):
        self.sock = sock
        self.ack_queue = ack_queue
        self.seq_num = 1
        self.ack_event = threading.Event()
        self.expected_ack = None
        self.send_lock = threading.Lock()  # Prevent concurrent sends

    # completely new send with ack function that implements a queue instead of recvfrom
    # this allows the host, joiner, and spectator peers to each implement their own
    # listener loops with unique logic
    def send_with_ack(self, message, addr, timeout=2.0):
        # Lock to prevent multiple concurrent sends from interfering
        with self.send_lock:
            message["sequence_number"] = str(self.seq_num)
            encoded = encode_message(message)
            data = encoded.encode("utf-8")

            for attempt in range(3):
                print(f"Attempt {attempt + 1}: Sending seq={self.seq_num}")
                self.sock.sendto(data, addr)

                expected_ack = self.seq_num
                
                # Clear any stale messages from queue before waiting
                messages_to_requeue = []

                # Check queue for ACKs from listener
                start_time = time.time()
                ack_received = False
                while time.time() - start_time < timeout:
                    try:
                        msg = self.ack_queue.get(timeout=0.1)  # Use blocking get with short timeout
                        if msg.get("message_type") == "ACK":
                            ack_num = int(msg.get("ack_number", -1))
                            if ack_num == expected_ack:
                                self.seq_num += 1
                                print("Ack received")
                                ack_received = True
                                break
                            else:
                                # ACK for different sequence - put it back for other threads
                                messages_to_requeue.append(msg)
                        else:
                            # Non-ACK message - put it back in the queue
                            messages_to_requeue.append(msg)
                    except Empty:
                        # Queue is empty, continue waiting
                        continue

                # Put back any messages that weren't for us
                for m in messages_to_requeue:
                    self.ack_queue.put(m)

                if ack_received:
                    return True

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