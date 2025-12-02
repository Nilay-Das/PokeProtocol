"""
=============================================================================
JOINER PEER - The Battle Client
=============================================================================

WHAT IS THIS FILE?
------------------
This file implements the Joiner peer. The Joiner is like a client that:
1. Connects to a Host that's already waiting
2. Receives the random seed from the Host
3. Exchanges Pokemon information
4. Participates in the battle (goes second)

WHAT DOES THE JOINER DO?
------------------------
1. CONNECT PHASE:
   - Send HANDSHAKE_REQUEST to the Host
   - Wait for HANDSHAKE_RESPONSE (contains the random seed)
   - Initialize RNG with the received seed

2. SETUP PHASE:
   - Send BATTLE_SETUP with our Pokemon info
   - Receive Host's BATTLE_SETUP
   - Battle is ready to begin!

3. BATTLE PHASE:
   - Wait for Host's first attack (Host goes first)
   - Take turns attacking
   - Handle chat messages

4. END PHASE:
   - Send or receive GAME_OVER
   - Close connections


KEY DIFFERENCE FROM HOST
------------------------
- Host: Creates the game, picks the seed, goes first
- Joiner: Joins an existing game, receives the seed, goes second

=============================================================================
"""

import threading
import time

from peers.base_peer import BasePeer
from protocol.messages import encode_message, decode_message
from protocol.message_factory import MessageFactory


class Joiner(BasePeer):
    """
    The Joiner peer that connects to a Host and participates in battle.
    
    The Joiner:
    - Connects to a Host at a known IP address and port
    - Receives the random seed from the Host's HANDSHAKE_RESPONSE
    - Goes second in battle (is_my_turn starts as False)
    
    Inherits common functionality from BasePeer.
    """

    def __init__(self, pokemon, db, comm_mode: str):
        """
        Initialize the Joiner peer.
        
        Args:
            pokemon: The Joiner's Pokemon for battle
            db: The Pokemon database
            comm_mode: "P2P" for direct connection, "BROADCAST" for local network
        """
        # Call parent class constructor
        # is_host=False means we go second in battle
        super().__init__(pokemon, db, comm_mode, is_host=False)

        # =====================================================================
        # JOINER-SPECIFIC ATTRIBUTES
        # =====================================================================
        
        # The random seed from the Host's HANDSHAKE_RESPONSE
        # We wait for this before starting the battle
        self.seed = None

    def start(self, host_ip: str, host_port: int):
        """
        Start the Joiner and connect to a Host.
        
        This function:
        1. Binds our socket to a local port
        2. Sends a HANDSHAKE_REQUEST to the Host
        3. Waits for the Host to accept us
        4. Starts the battle when connected
        
        Args:
            host_ip: The IP address of the Host
            host_port: The port number the Host is listening on
        """
        # Step 1: Bind our socket to a local port
        if self.comm_mode == "P2P":
            # In P2P mode, let the system pick a free port for us
            # ("", 0) means "any IP, any available port"
            self.sock.bind(("", 0))
        else:
            # In BROADCAST mode, we need to be on the same port as the Host
            self.sock.bind(("0.0.0.0", host_port))
        
        # Step 2: Get our display name
        self.name = input("Enter your name: ")
        
        # Step 3: Start the listener loop in a background thread
        self.running = True
        listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
        listener_thread.start()
        
        # Step 4: Send HANDSHAKE_REQUEST to the Host
        self._send_handshake(host_ip, host_port)
        
        print("[JOINER] Handshake sent. Waiting for Host to accept...")
        print("(If the Host doesn't respond, press Ctrl+C to exit)")
        
        # Step 5: Wait for the Host to send us the seed
        # The seed comes in the HANDSHAKE_RESPONSE message
        while self.seed is None:
            time.sleep(0.5)  # Check every half second
        
        print("[JOINER] Connected! Received seed from Host.")
        
        # Step 6: Send our BATTLE_SETUP to the Host
        self._send_battle_setup()
        
        # Step 7: Start the chat loop (runs in main thread)
        print("\n--- Battle Ready! ---")
        print("Waiting for Host to make the first move...")
        while True:
            self.chat()

    def _send_handshake(self, host_ip: str, host_port: int):
        """
        Send a HANDSHAKE_REQUEST to the Host.
        
        This is the first step in connecting to a battle.
        We send this message and wait for the Host to accept us.
        
        Args:
            host_ip: The IP address of the Host
            host_port: The port number the Host is listening on
        """
        # Store the Host's address
        self.remote_addr = (host_ip, host_port)
        
        # Create and send the HANDSHAKE_REQUEST
        handshake_request = MessageFactory.handshake_request()
        encoded_message = encode_message(handshake_request)
        self.sock.sendto(encoded_message.encode("utf-8"), self.remote_addr)
        
        print(f"[JOINER] Sent HANDSHAKE_REQUEST to {host_ip}:{host_port}")

    def _send_battle_setup(self):
        """
        Send our BATTLE_SETUP message to the Host.
        
        This tells the Host what Pokemon we're using and our stat boost
        allocation. After both peers exchange BATTLE_SETUP, the battle
        can begin!
        """
        # Create the BATTLE_SETUP message
        battle_setup = MessageFactory.battle_setup(
            communication_mode=self.comm_mode,
            pokemon_name=self.pokemon.name,
        )
        
        print(f"[JOINER] Sending BATTLE_SETUP: {self.pokemon.name}")
        
        # Use reliability layer to ensure it's delivered
        self.reliability.send_with_ack(battle_setup, self.remote_addr)

    def process_message(self, message: dict, sender_address: tuple):
        """
        Process a received message with Joiner-specific handling.
        
        The Joiner has some extra responsibilities:
        - Extract the seed from HANDSHAKE_RESPONSE
        
        Args:
            message: The decoded message dictionary
            sender_address: The (IP, port) of who sent it
        """
        # Check if this message contains the seed (from HANDSHAKE_RESPONSE)
        if "seed" in message and self.seed is None:
            # Extract and store the seed
            seed_value = int(message["seed"])
            self.seed = seed_value
            
            # Initialize our RNG with the same seed as the Host
            self.initialize_rng(seed_value)
        
        # For all other message handling, use the parent class
        super().process_message(message, sender_address)

    # chat() method is inherited from BasePeer


# Alias for backwards compatibility
# This allows code to use either `Joiner` or `joiner` to refer to the class
joiner = Joiner
