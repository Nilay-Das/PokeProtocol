"""
=============================================================================
HOST PEER - The Battle Server
=============================================================================

WHAT IS THIS FILE?
------------------
This file implements the Host peer. The Host is like a server that:
1. Waits for other players (Joiners) to connect
2. Accepts or rejects connection requests
3. Sets up the battle with a shared random seed
4. Optionally allows spectators to watch

WHAT DOES THE HOST DO?
----------------------
1. SETUP PHASE:
   - Bind to an IP address and port
   - Start listening for connection requests
   
2. CONNECTION PHASE:
   - Receive HANDSHAKE_REQUEST from Joiner
   - Ask user if they want to accept the connection
   - If yes, send HANDSHAKE_RESPONSE with a random seed

3. BATTLE PHASE:
   - Exchange BATTLE_SETUP messages
   - Take turns attacking (Host goes first!)
   - Handle chat messages
   - Forward messages to spectators (if any)

4. END PHASE:
   - Send or receive GAME_OVER
   - Close connections

=============================================================================
"""

import socket
import threading
import queue

from peers.base_peer import BasePeer
from protocol.messages import encode_message, decode_message
from protocol.battle_state import BattlePhase
from protocol.message_factory import MessageFactory
from protocol.constants import MessageType


class Host(BasePeer):
    """
    The Host peer that accepts connections and manages the battle.
    
    The Host:
    - Listens on a specific port for incoming connections
    - Chooses the random seed for synchronized damage calculations
    - Always goes first in battle (is_my_turn starts as True)
    - Can accept spectators to watch the battle
    
    Inherits common functionality from BasePeer.
    """

    def __init__(self, pokemon, db, comm_mode: str):
        """
        Initialize the Host peer.
        
        Args:
            pokemon: The Host's Pokemon for battle
            db: The Pokemon database
            comm_mode: "P2P" for direct connection, "BROADCAST" for local network
        """
        # Call parent class constructor
        # is_host=True means we go first in battle
        super().__init__(pokemon, db, comm_mode, is_host=True)

        # =====================================================================
        # HOST-SPECIFIC ATTRIBUTES
        # =====================================================================
        
        # The IP address we'll listen on
        self.host_address = ""
        
        # The random seed for synchronized RNG
        self.seed = 0
        
        # Queue for incoming connection requests
        # We put requests here so we can process them one at a time
        self.request_queue = queue.Queue()
        
        # Have we sent our BATTLE_SETUP yet?
        self.battle_setup_done = False

        # =====================================================================
        # SPECTATOR SUPPORT
        # =====================================================================
        
        # Is a spectator connected?
        self.spectator_connected = False
        
        # The spectator's address (IP, port)
        self.spectator_address = None

    def accept(self):
        """
        Main function to start the Host and accept connections.
        
        This function:
        1. Gets the Host's name and network settings
        2. Binds the socket to an address and port
        3. Waits for a Joiner to connect
        4. Starts the battle when connection is accepted
        """
        # Step 1: Get the Host's display name
        self.name = input("Enter your name: ")
        
        # Step 2: Get the IP address to listen on
        if self.comm_mode == "P2P":
            # In P2P mode, we need a specific IP address
            self.host_address = input("Enter your IP address: ")
        else:
            # In BROADCAST mode, we listen on all interfaces
            self.host_address = "0.0.0.0"  # 0.0.0.0 means "all network interfaces"
        
        # Step 3: Get the port number
        print("Enter a port number (must be above 5000):")
        port = 5000
        while port <= 5000:
            try:
                port = int(input())
                if port <= 5000:
                    print("Port must be above 5000. Try again:")
            except ValueError:
                print("Please enter a valid number:")
        
        # Step 4: Bind the socket to the address and port
        # After this, we can receive messages at this address
        self.sock.bind((self.host_address, port))
        print(f"\n{self.name} is now listening on port {port}")
        print("Waiting for a Joiner to connect...")
        
        # Step 5: Start the accept loop in a background thread
        # This loop listens for HANDSHAKE_REQUEST messages
        self.running = True
        accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        accept_thread.start()
        
        # Step 6: Main loop - process connection requests
        while True:
            # Check if there's a pending connection request
            if not self.request_queue.empty():
                # Get the request from the queue
                request_message, joiner_address = self.request_queue.get()
                
                print(f"\n--- Connection Request ---")
                print(f"Address: {joiner_address}")
                print(f"Message: {request_message}")
                
                # Ask the user if they want to accept
                choice = input("\nAccept this connection? (Y/N): ").upper()
                
                if choice != "Y":
                    print("Connection rejected.")
                    continue
                
                # Store the Joiner's address
                if self.comm_mode == "P2P":
                    self.remote_addr = joiner_address
                else:
                    # In broadcast mode, send to everyone
                    self.remote_addr = ("255.255.255.255", port)
                
                # Stop the accept loop (we have our Joiner)
                self.running = False
                
                # Get the random seed for synchronized RNG
                seed = -1
                while seed < 0:
                    try:
                        seed = int(input("Enter a random seed (any positive number): "))
                        if seed < 0:
                            print("Seed must be positive.")
                    except ValueError:
                        print("Please enter a valid number.")
                
                # Send HANDSHAKE_RESPONSE with the seed
                self.seed = seed
                handshake_response = MessageFactory.handshake_response(seed)
                encoded_response = encode_message(handshake_response)
                self.sock.sendto(encoded_response.encode("utf-8"), self.remote_addr)
                print(f"Handshake sent with seed: {seed}")
                
                # Initialize our RNG with the same seed
                self.initialize_rng(seed)
                
                # Start the listener loop in a background thread
                listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
                listener_thread.start()
                
                # Start the chat loop (this runs in the main thread)
                print("\n--- Battle Ready! ---")
                print("You go first! Type !attack to make a move.")
                while True:
                    self.chat()
        
        # Clean up (we never actually reach here in the current code)
        self.sock.close()
        accept_thread.join()

    def _accept_loop(self):
        """
        Background loop that listens for HANDSHAKE_REQUEST messages.
        
        This runs in a separate thread so the main thread can handle
        user input while we wait for connections.
        
        When we receive a HANDSHAKE_REQUEST, we put it in the request_queue
        so the main thread can decide whether to accept it.
        """
        while self.running:
            try:
                # Wait for a message (blocks until one arrives)
                raw_message, sender_address = self.sock.recvfrom(1024)
            except OSError:
                # Socket was closed, exit the loop
                break
            
            # Decode the message
            message_string = raw_message.decode("utf-8")
            message_dict = decode_message(message_string)
            
            # Only process HANDSHAKE_REQUEST in this loop
            # All other messages are handled by the listen_loop later
            if message_dict.get("message_type") == "HANDSHAKE_REQUEST":
                # Put the request in the queue for the main thread
                self.request_queue.put((message_string, sender_address))
        
        # Reset socket timeout when exiting
        try:
            self.sock.settimeout(None)
        except OSError:
            pass

    def process_message(self, message: dict, sender_address: tuple):
        """
        Process a received message with Host-specific handling.
        
        The Host has some extra responsibilities:
        - Forward messages to spectators (if any)
        - Handle SPECTATOR_REQUEST messages
        
        Args:
            message: The decoded message dictionary
            sender_address: The (IP, port) of who sent it
        """
        # If a spectator is connected and we're in P2P mode,
        # forward all messages to the spectator
        if self.spectator_connected and self.comm_mode == "P2P":
            self.reliability.send_with_ack(message, self.spectator_address)
        
        # Handle SPECTATOR_REQUEST (someone wants to watch the battle)
        message_type = message.get("message_type")
        if message_type == MessageType.SPECTATOR_REQUEST:
            self._handle_spectator_request(sender_address)
            return  # Don't process this as a normal message
        
        # For all other messages, use the parent class handler
        super().process_message(message, sender_address)

    def _handle_spectator_request(self, spectator_address: tuple):
        """
        Handle a SPECTATOR_REQUEST - someone wants to watch the battle.
        
        Args:
            spectator_address: The (IP, port) of the spectator
        """
        # Only allow one spectator
        if self.spectator_connected:
            print("A spectator is already connected.")
            return
        
        # Store the spectator's address
        self.spectator_address = spectator_address
        
        # Send a handshake response (no seed needed for spectators)
        response_message = {"message_type": MessageType.HANDSHAKE_RESPONSE}
        encoded_response = encode_message(response_message)
        self.sock.sendto(encoded_response.encode("utf-8"), spectator_address)
        
        # Mark spectator as connected
        self.spectator_connected = True
        print(f"Spectator connected from {spectator_address}")

    def _on_battle_setup(self, message: dict):
        """
        Called when we receive the Joiner's BATTLE_SETUP message.
        
        After the Joiner sends their Pokemon info, we need to send ours.
        This completes the battle setup and the fight can begin!
        
        Args:
            message: The BATTLE_SETUP message from the Joiner
        """
        # Only send our BATTLE_SETUP once
        if self.battle_setup_done:
            return
        
        # Make sure we have a remote address
        if self.remote_addr is None:
            return
        
        # Create our BATTLE_SETUP message
        our_battle_setup = MessageFactory.battle_setup(
            communication_mode=self.comm_mode,
            pokemon_name=self.pokemon.name,
        )
        
        print(f"[HOST] Sending BATTLE_SETUP: {our_battle_setup}")
        self.battle_setup_done = True
        
        # Send in a background thread to avoid blocking
        def send_battle_setup():
            self.reliability.send_with_ack(our_battle_setup, self.remote_addr)
        
        sender_thread = threading.Thread(target=send_battle_setup, daemon=True)
        sender_thread.start()

    def send_message(self, message: dict):
        """
        Send a message to the Joiner and optionally to spectators.
        
        The Host overrides this to forward messages to spectators
        when they're connected.
        
        Args:
            message: The message dictionary to send
        """
        # Send to the Joiner
        self.reliability.send_with_ack(message, self.remote_addr)
        
        # Also send to spectator if connected (P2P mode only)
        if self.spectator_connected and self.comm_mode == "P2P":
            self.reliability.send_with_ack(message, self.spectator_address)

    # chat() method is inherited from BasePeer


# Alias for backwards compatibility
# This allows code to use either `Host` or `host` to refer to the class
host = Host
