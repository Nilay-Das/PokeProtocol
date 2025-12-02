"""
Makes UDP reliable by adding retries and acknowledgments.
UDP doesnt guarantee delivery so we add our own system on top.
"""

import threading
import time
from queue import Queue, Empty

from protocol.messages import encode_message


# how long to wait for ACK before retrying
TIMEOUT_SECONDS = 0.5

# how many times to try before giving up
MAX_RETRY_ATTEMPTS = 3

# how often to check for ACKs
QUEUE_CHECK_INTERVAL = 0.1


class ReliableChannel:
    """Wraps a UDP socket to make it reliable with retries and ACKs."""

    def __init__(self, sock, ack_queue: Queue):
        """Sets up the reliable channel with a socket and queue for ACKs."""
        
        self.sock = sock
        self.ack_queue = ack_queue
        self.sequence_number = 1
        self.send_lock = threading.Lock()

    def send_with_ack(self, message: dict, destination_address: tuple) -> bool:
        """Sends a message and waits for ACK. Returns True if delivered."""
        
        # lock so only one thread sends at a time
        with self.send_lock:
            return self._send_message_with_retries(message, destination_address)

    def _send_message_with_retries(self, message: dict, destination_address: tuple) -> bool:
        """Actually sends the message with retries."""
        
        # add sequence number
        current_sequence = self.sequence_number
        message["sequence_number"] = str(current_sequence)
        
        # convert to bytes
        message_as_string = encode_message(message)
        message_as_bytes = message_as_string.encode("utf-8")
        
        # try sending up to MAX_RETRY_ATTEMPTS times
        for attempt_number in range(1, MAX_RETRY_ATTEMPTS + 1):
            print(f"Attempt {attempt_number}: Sending message with seq={current_sequence}")
            
            self.sock.sendto(message_as_bytes, destination_address)
            
            # wait for ACK
            ack_was_received = self._wait_for_ack(current_sequence)
            
            if ack_was_received:
                self.sequence_number = self.sequence_number + 1
                print("ACK received - message delivered successfully!")
                return True
            else:
                print(f"Timeout - no ACK received for seq={current_sequence}")
        
        print(f"FAILED: Could not deliver message after {MAX_RETRY_ATTEMPTS} attempts")
        return False

    def _wait_for_ack(self, expected_sequence_number: int) -> bool:
        """Waits for an ACK with the right sequence number."""
        
        start_time = time.time()
        messages_to_put_back = []
        
        while True:
            # check if we timed out
            elapsed_time = time.time() - start_time
            if elapsed_time >= TIMEOUT_SECONDS:
                self._put_messages_back(messages_to_put_back)
                return False
            
            # try to get a message from queue
            message = self._get_message_from_queue()
            
            if message is None:
                continue
            
            # check if its the ACK we want
            if self._is_matching_ack(message, expected_sequence_number):
                self._put_messages_back(messages_to_put_back)
                return True
            else:
                # not our ACK, save it for later
                messages_to_put_back.append(message)

    def _get_message_from_queue(self) -> dict:
        """Tries to get a message from the ACK queue."""
        
        try:
            message = self.ack_queue.get(timeout=QUEUE_CHECK_INTERVAL)
            return message
        except Empty:
            return None

    def _is_matching_ack(self, message: dict, expected_sequence_number: int) -> bool:
        """Checks if this is the ACK we're waiting for."""
        
        message_type = message.get("message_type", "")
        if message_type != "ACK":
            return False
        
        ack_number_string = message.get("ack_number", "-1")
        ack_number = int(ack_number_string)
        
        return ack_number == expected_sequence_number

    def _put_messages_back(self, messages: list):
        """Puts messages back in the queue so other code can use them."""
        
        for message in messages:
            self.ack_queue.put(message)
