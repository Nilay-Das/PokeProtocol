"""
=============================================================================
RELIABLE CHANNEL - Making UDP Reliable
=============================================================================

WHAT IS THIS FILE?
------------------
This file solves a fundamental problem with UDP (User Datagram Protocol):
UDP does NOT guarantee that messages arrive!

Think of UDP like sending a postcard - you drop it in the mailbox and hope
it arrives, but you never know for sure. Sometimes postcards get lost.

TCP (Transmission Control Protocol) is like sending a certified letter -
you get confirmation that it arrived. But TCP is slower and more complex.

OUR SOLUTION: We use UDP (fast!) but add our own reliability on top.


HOW DOES RELIABILITY WORK?
--------------------------
We use a simple system called "Stop-and-Wait ARQ" (Automatic Repeat Request):

1. SENDER adds a sequence number to each message (1, 2, 3, ...)
2. SENDER sends the message and starts a timer
3. RECEIVER gets the message and sends back an "ACK" (acknowledgment)
   with the same sequence number
4. SENDER receives the ACK and knows the message arrived safely

If the timer runs out before getting an ACK, we try again (up to 3 times).


EXAMPLE MESSAGE FLOW:
--------------------
    SENDER                              RECEIVER
      |                                    |
      |--- Message (seq=1) --------------->|
      |                                    |
      |<-------------- ACK (ack_num=1) ----|
      |                                    |
      |--- Message (seq=2) ----X  (LOST!)  |
      |                                    |
      | (timeout - no ACK received)        |
      |                                    |
      |--- Message (seq=2) --------------->|  (retry!)
      |                                    |
      |<-------------- ACK (ack_num=2) ----|
      |                                    |


WHY DO WE NEED THIS?
--------------------
In a Pokemon battle, we MUST know that attack announcements, damage
calculations, and game over messages arrive. If a GAME_OVER message
gets lost, one player thinks the battle is over while the other doesn't!

=============================================================================
"""

import threading
import time
from queue import Queue, Empty

from protocol.messages import encode_message


# ============================================================================
# CONFIGURATION - These values come from the RFC specification
# ============================================================================

# How long to wait for an ACK before retrying (in seconds)
# The RFC specifies 500 milliseconds = 0.5 seconds
TIMEOUT_SECONDS = 0.5

# How many times to retry sending before giving up
# The RFC specifies 3 attempts total
MAX_RETRY_ATTEMPTS = 3

# How often to check the queue for ACK messages (in seconds)
# This is a small value so we respond quickly
QUEUE_CHECK_INTERVAL = 0.1


class ReliableChannel:
    """
    A wrapper around a UDP socket that adds reliability.
    
    This class ensures messages are delivered by:
    1. Adding sequence numbers to track each message
    2. Waiting for acknowledgments (ACKs) from the receiver
    3. Retrying if no ACK is received within the timeout period
    
    Example usage:
        # Create a UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Create a queue where received ACKs will be placed
        ack_queue = Queue()
        
        # Create the reliable channel
        channel = ReliableChannel(sock, ack_queue)
        
        # Send a message and wait for confirmation
        message = {"message_type": "ATTACK_ANNOUNCE", "move_name": "Thunderbolt"}
        success = channel.send_with_ack(message, ("192.168.1.100", 5001))
        
        if success:
            print("Message was delivered!")
        else:
            print("Failed to deliver message after 3 attempts")
    """

    def __init__(self, sock, ack_queue: Queue):
        """
        Initialize the reliable channel.
        
        Args:
            sock: A UDP socket (already created with socket.socket())
                  This is the actual network connection we'll use to send data.
            
            ack_queue: A Queue where the listener thread will put ACK messages.
                       When we receive an ACK from the other peer, it goes here
                       so we know our message was received.
        
        How it works:
            - The main program has a "listener loop" running in a background thread
            - When that listener receives an ACK message, it puts it in ack_queue
            - This class checks ack_queue to see if our message was acknowledged
        """
        # The UDP socket we'll use to send messages
        self.sock = sock
        
        # Queue where ACK messages from the listener will appear
        self.ack_queue = ack_queue
        
        # The next sequence number to use (starts at 1)
        # Each message gets a unique number so we can match ACKs to messages
        self.sequence_number = 1
        
        # A lock to prevent two threads from sending at the same time
        # Without this, sequence numbers could get mixed up!
        self.send_lock = threading.Lock()

    def send_with_ack(self, message: dict, destination_address: tuple) -> bool:
        """
        Send a message and wait for acknowledgment.
        
        This is the main function you'll use. It:
        1. Adds a sequence number to your message
        2. Sends it over UDP
        3. Waits for an ACK
        4. Retries up to 3 times if needed
        
        Args:
            message: A dictionary containing the message to send.
                     Example: {"message_type": "ATTACK_ANNOUNCE", "move_name": "Tackle"}
            
            destination_address: A tuple of (IP address, port number).
                                Example: ("192.168.1.100", 5001)
        
        Returns:
            True if the message was acknowledged (delivered successfully)
            False if all retry attempts failed
        
        Example:
            message = {"message_type": "CHAT_MESSAGE", "text": "Hello!"}
            address = ("192.168.1.50", 5001)
            
            if channel.send_with_ack(message, address):
                print("Message sent successfully!")
            else:
                print("Failed to send message - peer might be offline")
        """
        # Use a lock so only one thread can send at a time
        # This prevents sequence number confusion
        with self.send_lock:
            return self._send_message_with_retries(message, destination_address)

    def _send_message_with_retries(self, message: dict, destination_address: tuple) -> bool:
        """
        Internal method that handles the actual sending and retry logic.
        
        This is separated from send_with_ack to keep the code organized.
        """
        # Step 1: Add a sequence number to the message
        # This lets the receiver know which message we sent
        # and lets us match the ACK to our specific message
        current_sequence = self.sequence_number
        message["sequence_number"] = str(current_sequence)
        
        # Step 2: Convert the message dictionary to a string, then to bytes
        # Networks send bytes (raw data), not Python dictionaries
        message_as_string = encode_message(message)
        message_as_bytes = message_as_string.encode("utf-8")
        
        # Step 3: Try to send the message (up to MAX_RETRY_ATTEMPTS times)
        for attempt_number in range(1, MAX_RETRY_ATTEMPTS + 1):
            print(f"Attempt {attempt_number}: Sending message with seq={current_sequence}")
            
            # Send the message over UDP
            self.sock.sendto(message_as_bytes, destination_address)
            
            # Wait for an ACK
            ack_was_received = self._wait_for_ack(current_sequence)
            
            if ack_was_received:
                # Success! Increment sequence number for the next message
                self.sequence_number = self.sequence_number + 1
                print("ACK received - message delivered successfully!")
                return True
            else:
                # No ACK received within timeout
                print(f"Timeout - no ACK received for seq={current_sequence}")
        
        # If we get here, all attempts failed
        print(f"FAILED: Could not deliver message after {MAX_RETRY_ATTEMPTS} attempts")
        return False

    def _wait_for_ack(self, expected_sequence_number: int) -> bool:
        """
        Wait for an ACK message with the expected sequence number.
        
        This method checks the ack_queue repeatedly until either:
        - We find an ACK with the right sequence number (return True)
        - We run out of time (return False)
        
        Args:
            expected_sequence_number: The sequence number we're waiting for.
                                     We only accept an ACK that matches this.
        
        Returns:
            True if we received the correct ACK
            False if we timed out waiting
        """
        # Keep track of when we started waiting
        start_time = time.time()
        
        # Messages that we pulled from the queue but weren't what we wanted
        # We'll put these back at the end so other code can use them
        messages_to_put_back = []
        
        # Keep checking until we run out of time
        while True:
            # Check if we've been waiting too long
            elapsed_time = time.time() - start_time
            if elapsed_time >= TIMEOUT_SECONDS:
                # Time's up! Put back any messages we borrowed and return False
                self._put_messages_back(messages_to_put_back)
                return False
            
            # Try to get a message from the queue
            message = self._get_message_from_queue()
            
            if message is None:
                # Queue was empty, keep waiting
                continue
            
            # Check if this is the ACK we're looking for
            if self._is_matching_ack(message, expected_sequence_number):
                # Found it! Put back any other messages and return True
                self._put_messages_back(messages_to_put_back)
                return True
            else:
                # This message isn't for us - save it to put back later
                messages_to_put_back.append(message)

    def _get_message_from_queue(self) -> dict:
        """
        Try to get a message from the ACK queue.
        
        Returns:
            The message dictionary if one was available
            None if the queue was empty
        """
        try:
            # Wait a short time for a message to appear
            # If no message arrives in QUEUE_CHECK_INTERVAL seconds, raise Empty
            message = self.ack_queue.get(timeout=QUEUE_CHECK_INTERVAL)
            return message
        except Empty:
            # No message available right now
            return None

    def _is_matching_ack(self, message: dict, expected_sequence_number: int) -> bool:
        """
        Check if a message is an ACK with the sequence number we want.
        
        Args:
            message: The message dictionary to check
            expected_sequence_number: The sequence number we're looking for
        
        Returns:
            True if this is the ACK we want
            False otherwise
        """
        # First, check if this is an ACK message
        message_type = message.get("message_type", "")
        if message_type != "ACK":
            return False
        
        # Get the ack_number from the message
        # Default to -1 if not found (which won't match any valid sequence)
        ack_number_string = message.get("ack_number", "-1")
        ack_number = int(ack_number_string)
        
        # Check if the ack_number matches what we're looking for
        return ack_number == expected_sequence_number

    def _put_messages_back(self, messages: list):
        """
        Put messages back into the queue so other code can use them.
        
        When we're looking for a specific ACK, we might pull out other
        messages by accident. This puts them back where they belong.
        
        Args:
            messages: A list of message dictionaries to put back
        """
        for message in messages:
            self.ack_queue.put(message)
