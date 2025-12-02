"""
=============================================================================
BASE PEER - Common Functionality for Host and Joiner
=============================================================================

WHAT IS THIS FILE?
------------------
This file contains the BasePeer class, which has all the code shared between
the Host and Joiner. Instead of writing the same code twice, we put it here
and have both Host and Joiner inherit from BasePeer.

This is called "inheritance" in object-oriented programming:
- Host IS-A BasePeer (with extra host-specific stuff)
- Joiner IS-A BasePeer (with extra joiner-specific stuff)


NETWORKING BASICS
-----------------

WHAT IS A SOCKET?
    A socket is like a phone line for your program. It lets you send and
    receive data over a network. You create a socket, connect it to an
    address (IP + port), and then send/receive data.

WHAT IS UDP?
    UDP (User Datagram Protocol) is one way to send data over a network.
    It's like sending a postcard:
    - Fast (no waiting for confirmation)
    - Simple (just send and forget)
    - Unreliable (might get lost!)
    
    We use UDP because it's fast, and we add our own reliability layer
    (see reliability.py) to make sure messages arrive.

WHAT IS AN IP ADDRESS?
    An IP address identifies a computer on a network.
    - "192.168.1.100" - a typical home network address
    - "127.0.0.1" - localhost (this computer)
    - "255.255.255.255" - broadcast (everyone on local network)

WHAT IS A PORT?
    A port is like an apartment number. The IP address gets you to the
    building (computer), and the port gets you to the specific apartment
    (program). Port numbers go from 0 to 65535.
    - We use ports above 5000 to avoid conflicts with system services


THREADING BASICS
----------------

WHAT IS A THREAD?
    A thread is like having multiple workers in your program. While one
    worker waits for network messages, another can handle user input.
    
    Without threads, our program would freeze every time it waited for
    a message to arrive!

OUR THREADS:
    1. Main thread: Handles user input (chat commands, attacks)
    2. Listener thread: Waits for incoming network messages


HOW MESSAGES FLOW
-----------------

    [USER INPUT] ---> [Main Thread] ---> [Send via Socket] ---> [Network]
                                                                    |
                                                                    v
    [Process] <--- [Listener Thread] <--- [Receive via Socket] <---+

=============================================================================
"""

import socket
import threading
import queue

from protocol.messages import encode_message, decode_message
from protocol.reliability import ReliableChannel
from protocol.battle_manager import BattleManager
from protocol.battle_state import BattlePhase, initialize_battle_rng
from protocol import message_handlers
from protocol.message_factory import MessageFactory
from protocol.constants import MessageType


class BasePeer:
    """
    Base class for peer implementations (Host and Joiner).
    
    This class provides:
    - Socket setup for network communication
    - A listener loop that runs in a background thread
    - Message handling for all battle protocol messages
    - Chat functionality
    - Attack functionality
    
    Both Host and Joiner inherit from this class to get all this
    functionality without duplicating code.
    """

    def __init__(self, pokemon, db, comm_mode: str, is_host: bool = True):
        """
        Initialize the base peer with all the common setup.
        
        Args:
            pokemon: Our Pokemon for this battle. Can be None for spectators.
            
            db: The Pokemon database (dictionary of all Pokemon).
                Used to look up opponent's Pokemon by name.
            
            comm_mode: How we communicate with other peers.
                       "P2P" - Direct peer-to-peer communication
                       "BROADCAST" - Send to everyone on local network
            
            is_host: Are we the host (True) or joiner (False)?
                    The host goes first in battle.
        """
        # =====================================================================
        # POKEMON AND BATTLE INFO
        # =====================================================================
        
        # Our Pokemon for this battle
        self.pokemon = pokemon
        
        # The opponent's Pokemon (set when we receive BATTLE_SETUP)
        self.opp_mon = None
        
        # The Pokemon database for looking up Pokemon by name
        self.db = db
        
        # Are we the host or joiner?
        self.is_host = is_host
        
        # Our display name
        self.name = ""
        
        # Communication mode: "P2P" or "BROADCAST"
        self.comm_mode = comm_mode

        # =====================================================================
        # SOCKET SETUP
        # =====================================================================
        # A socket is our connection to the network.
        # We use UDP (SOCK_DGRAM) for fast, connectionless communication.
        
        # Create a UDP socket
        # AF_INET = IPv4 addresses (like 192.168.1.100)
        # SOCK_DGRAM = UDP (datagram, no connection)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Allow broadcast messages (sending to 255.255.255.255)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Allow reusing the address (helpful when restarting quickly)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # =====================================================================
        # MESSAGE HANDLING
        # =====================================================================
        
        # Queue for ACK messages from the listener thread
        # The reliability layer checks this to know if messages were received
        self.ack_queue = queue.Queue()
        
        # History of all received messages (for debugging)
        self.kv_messages = []
        
        # Lock to prevent race conditions when accessing shared data
        # A race condition is when two threads try to modify the same data
        self.lock = threading.Lock()
        
        # Sequence number of the last message we processed
        # Used to detect and ignore duplicate messages
        self.last_processed_sequence = 0
        
        # Last ACK number we received (for debugging)
        self.ack = None

        # =====================================================================
        # STATE FLAGS
        # =====================================================================
        
        # Is the peer actively running?
        self.running = False
        
        # Should the listener loop continue?
        self.listening = True

        # =====================================================================
        # RELIABILITY LAYER
        # =====================================================================
        # Wraps our socket to add reliability (retries, ACKs)
        
        self.reliability = ReliableChannel(self.sock, self.ack_queue)

        # =====================================================================
        # BATTLE MANAGER
        # =====================================================================
        # Manages battle state (turns, damage calculations, etc.)
        
        self.battle_manager = BattleManager(is_host=is_host)

        # =====================================================================
        # REMOTE PEER
        # =====================================================================
        
        # The address (IP, port) of the other peer we're communicating with
        self.remote_addr = None
        
        # The random seed for synchronized RNG
        self.seed = None

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_role(self) -> str:
        """
        Get our role as a string for logging.
        
        Returns:
            "HOST" if we're the host, "JOINER" otherwise
        """
        if self.is_host:
            return "HOST"
        else:
            return "JOINER"

    def initialize_rng(self, seed: int):
        """
        Initialize the random number generator with a shared seed.
        
        Both peers must use the same seed to get the same "random" numbers.
        This ensures damage calculations match.
        
        Args:
            seed: The seed value from HANDSHAKE_RESPONSE
        """
        self.seed = seed
        initialize_battle_rng(seed)
        role = self.get_role()
        print(f"[{role}] Battle RNG initialized with seed: {seed}")

    # =========================================================================
    # SEQUENCE NUMBER AND ACK HANDLING
    # =========================================================================

    def handle_sequence_and_ack(self, message: dict, sender_address: tuple) -> bool:
        """
        Handle the sequence number of an incoming message and send ACK.
        
        This is part of our reliability layer:
        1. Every message has a sequence number
        2. We send an ACK back for every message we receive
        3. We ignore duplicate messages (same sequence number seen before)
        
        Args:
            message: The decoded message dictionary
            sender_address: The (IP, port) of who sent the message
        
        Returns:
            True if this is a duplicate message (should be ignored)
            False if this is a new message (should be processed)
        """
        # Check if the message has a sequence number
        if "sequence_number" not in message:
            # No sequence number = not a reliable message, process it
            return False
        
        incoming_sequence = int(message["sequence_number"])
        
        # Always send an ACK back, even for duplicates
        # This is important! The sender might not have received our first ACK
        ack_message = MessageFactory.ack(incoming_sequence)
        ack_encoded = encode_message(ack_message)
        self.sock.sendto(ack_encoded.encode("utf-8"), sender_address)
        
        if self.is_host:
            print(f"[HOST] Sending ACK {incoming_sequence} to {sender_address}")
        
        # Check if this is a duplicate message
        if incoming_sequence <= self.last_processed_sequence:
            role = self.get_role()
            print(f"[{role}] Ignoring duplicate message (seq={incoming_sequence}, already processed up to {self.last_processed_sequence})")
            return True  # Duplicate, should be ignored
        
        # New message! Update our sequence counter
        self.last_processed_sequence = incoming_sequence
        return False  # Not a duplicate, should be processed

    def store_message(self, message: dict):
        """
        Store a message in our history (for debugging).
        
        Uses a lock to prevent race conditions with the listener thread.
        
        Args:
            message: The message dictionary to store
        """
        # Acquire the lock before modifying shared data
        with self.lock:
            self.kv_messages.append(message)

    # =========================================================================
    # MESSAGE PROCESSING
    # =========================================================================

    def process_message(self, message: dict, sender_address: tuple):
        """
        Process a received message by calling the appropriate handler.
        
        This is the main "router" that looks at the message type and
        calls the right handler function.
        
        Args:
            message: The decoded message dictionary
            sender_address: The (IP, port) of who sent the message
        """
        message_type = message.get("message_type")
        
        # =====================================================================
        # BATTLE_SETUP - Opponent is telling us their Pokemon
        # =====================================================================
        if message_type == MessageType.BATTLE_SETUP:
            message_handlers.handle_battle_setup(message, self, is_host=self.is_host)
            # Give subclasses a chance to respond (Host sends its own BATTLE_SETUP)
            self._on_battle_setup(message)
        
        # =====================================================================
        # ATTACK_ANNOUNCE - Opponent is attacking us!
        # =====================================================================
        elif message_type == MessageType.ATTACK_ANNOUNCE:
            # Get the response messages
            defense_msg, calculation_report_msg = message_handlers.handle_attack_announce(
                message, self, is_host=self.is_host
            )
            
            # Send both responses if we got them
            if defense_msg and calculation_report_msg:
                # Send in a background thread so we don't block
                def send_responses():
                    self.reliability.send_with_ack(defense_msg, self.remote_addr)
                    self.reliability.send_with_ack(calculation_report_msg, self.remote_addr)
                
                background_thread = threading.Thread(target=send_responses, daemon=True)
                background_thread.start()
        
        # =====================================================================
        # DEFENSE_ANNOUNCE - Opponent acknowledged our attack
        # =====================================================================
        elif message_type == MessageType.DEFENSE_ANNOUNCE:
            # Get our calculation report
            calculation_report = message_handlers.handle_defense_announce(
                message, self, is_host=self.is_host
            )
            
            # Send it if we got one
            if calculation_report:
                def send_report():
                    self.reliability.send_with_ack(calculation_report, self.remote_addr)
                
                background_thread = threading.Thread(target=send_report, daemon=True)
                background_thread.start()
        
        # =====================================================================
        # CALCULATION_REPORT - Compare damage calculations
        # =====================================================================
        elif message_type == MessageType.CALCULATION_REPORT:
            # Get the response (CONFIRM or RESOLUTION_REQUEST)
            response, game_over_msg, should_stop = message_handlers.handle_calculation_report(
                message, self, is_host=self.is_host
            )
            
            if response:
                if game_over_msg:
                    # Send confirm, then game over
                    def send_confirm_and_game_over():
                        self.reliability.send_with_ack(response, self.remote_addr)
                        self.send_message(game_over_msg)
                        self.running = False
                        self.listening = False
                    
                    background_thread = threading.Thread(target=send_confirm_and_game_over, daemon=True)
                    background_thread.start()
                else:
                    # Just send the response
                    def send_response():
                        self.reliability.send_with_ack(response, self.remote_addr)
                    
                    background_thread = threading.Thread(target=send_response, daemon=True)
                    background_thread.start()
        
        # =====================================================================
        # CALCULATION_CONFIRM - Opponent agrees with our calculation
        # =====================================================================
        elif message_type == MessageType.CALCULATION_CONFIRM:
            message_handlers.handle_calculation_confirm(message, self, is_host=self.is_host)
        
        # =====================================================================
        # RESOLUTION_REQUEST - Calculations didn't match
        # =====================================================================
        elif message_type == MessageType.RESOLUTION_REQUEST:
            game_over_msg, should_stop, is_fatal = message_handlers.handle_resolution_request(
                message, self, is_host=self.is_host
            )
            
            if game_over_msg:
                # Send game over and stop
                def send_game_over():
                    self.send_message(game_over_msg)
                    self.running = False
                    self.listening = False
                
                background_thread = threading.Thread(target=send_game_over, daemon=True)
                background_thread.start()
            elif is_fatal:
                # Fatal error, just stop
                self.running = False
                self.listening = False
        
        # =====================================================================
        # GAME_OVER - Battle is finished!
        # =====================================================================
        elif message_type == MessageType.GAME_OVER:
            message_handlers.handle_game_over(message, self, is_host=self.is_host)
            self.running = False
            self.listening = False
            self.sock.close()
        
        # =====================================================================
        # ACK - Track acknowledgment numbers (for debugging)
        # =====================================================================
        if "ack_number" in message:
            self.ack = int(message["ack_number"])

    def _on_battle_setup(self, message: dict):
        """
        Hook for subclasses to handle battle setup completion.
        
        The Host overrides this to send its own BATTLE_SETUP in response.
        The Joiner doesn't need to do anything extra.
        
        Args:
            message: The BATTLE_SETUP message we received
        """
        # Default implementation does nothing
        # Host overrides this
        pass

    # =========================================================================
    # LISTENER LOOP
    # =========================================================================

    def listen_loop(self):
        """
        Main loop that listens for incoming messages.
        
        This runs in a background thread so the main thread can handle
        user input. It continuously:
        1. Waits for a message to arrive
        2. Decodes the message
        3. Handles sequence numbers and ACKs
        4. Processes the message
        
        The loop exits when self.listening becomes False.
        """
        # Remove any timeout so recvfrom blocks until a message arrives
        try:
            self.sock.settimeout(None)
        except OSError:
            # Socket might already be closed
            return
        
        # Keep listening until we're told to stop
        while self.listening:
            try:
                # Wait for a message (this blocks until one arrives)
                raw_message, sender_address = self.sock.recvfrom(1024)
            except socket.timeout:
                # Shouldn't happen with no timeout, but just in case
                continue
            except OSError:
                # Socket was closed
                break
            
            # Decode the raw bytes into a string, then parse into a dictionary
            message_string = raw_message.decode("utf-8")
            message_dict = decode_message(message_string)
            
            # Print the message (unless it's an ACK, those are too noisy)
            if message_dict.get("message_type") != MessageType.ACK:
                print(f"\n{message_string}")
            
            # Put the message in the ACK queue for the reliability layer
            self.ack_queue.put(message_dict)
            
            # Handle sequence numbers and send ACK
            is_duplicate = self.handle_sequence_and_ack(message_dict, sender_address)
            if is_duplicate:
                # We've already processed this message, skip it
                continue
            
            # Store the message in our history
            self.store_message(message_dict)
            
            # Process the message (call the appropriate handler)
            self.process_message(message_dict, sender_address)

    # =========================================================================
    # SENDING MESSAGES
    # =========================================================================

    def send_message(self, message: dict):
        """
        Send a message to the remote peer with reliability.
        
        This uses the reliability layer to ensure the message is delivered.
        
        Args:
            message: The message dictionary to send
        """
        self.reliability.send_with_ack(message, self.remote_addr)

    def send_chat_message(self, text: str):
        """
        Send a text chat message to the opponent.
        
        Args:
            text: The text of the message
        """
        chat_message = MessageFactory.chat_text(self.name, text)
        self.send_message(chat_message)

    def send_sticker_message(self, sticker_data: str):
        """
        Send a sticker (image) to the opponent.
        
        Args:
            sticker_data: The sticker data (usually Base64 encoded)
        """
        sticker_message = MessageFactory.chat_sticker(self.name, sticker_data)
        self.send_message(sticker_message)

    # =========================================================================
    # ATTACK FUNCTIONALITY
    # =========================================================================

    def perform_attack(self) -> bool:
        """
        Perform an attack on the opponent.
        
        This function:
        1. Checks if we can attack (our turn, right phase)
        2. Shows available moves
        3. Asks if we want to use a special attack boost
        4. Sends the ATTACK_ANNOUNCE message
        
        Returns:
            True if the attack was initiated, False otherwise
        """
        role = self.get_role()
        bm = self.battle_manager
        
        # Check 1: Is it our turn?
        if not bm.is_my_turn:
            print(f"[{role}] It's not your turn! Wait for the opponent's move.")
            return False
        
        # Check 2: Are we in the right phase?
        if bm.battle_phase != BattlePhase.WAITING_FOR_MOVE:
            print(f"[{role}] Cannot attack right now. Current phase: {bm.battle_phase}")
            return False
        
        # Check 3: Do we know the opponent's Pokemon?
        if not self.opp_mon:
            print(f"[{role}] Cannot attack - opponent's Pokemon not set up yet.")
            return False
        
        # Show our Pokemon and available moves
        print(f"\nYour Pokemon: {self.pokemon.name}")
        
        # Choose a move
        if not self.pokemon.moves:
            # No moves in database, use a default
            print("No moves available, using BasicMove.")
            move_name = "BasicMove"
        else:
            print("Available moves:")
            for index, move in enumerate(self.pokemon.moves, start=1):
                print(f"  {index}. {move}")
            
            # Get user's choice
            choice = input("Choose a move number: ")
            try:
                index = int(choice) - 1
                if 0 <= index < len(self.pokemon.moves):
                    move_name = self.pokemon.moves[index]
                else:
                    print("Invalid choice, using first move.")
                    move_name = self.pokemon.moves[0]
            except ValueError:
                print("Invalid input, using first move.")
                move_name = self.pokemon.moves[0]
        
        # Ask about special attack boost
        if bm.special_attack_uses > 0:
            print(f"\nSpecial Attack boosts remaining: {bm.special_attack_uses}")
            use_boost_input = input("Use Special Attack boost? (y/n): ")
            if use_boost_input.lower().strip() == "y":
                bm.use_special_attack()
        
        # Prepare and send the attack
        attack_message = bm.prepare_attack(self.pokemon, self.opp_mon, move_name)
        print(f"[{role}] Sending ATTACK_ANNOUNCE: {move_name}")
        self.reliability.send_with_ack(attack_message, self.remote_addr)
        print(f"[{role}] Waiting for opponent's response...")
        
        return True

    # =========================================================================
    # CHAT INTERFACE
    # =========================================================================

    def chat(self):
        """
        Interactive chat interface for the player.
        
        Shows the current status and available commands:
        - !attack - Attack the opponent
        - !defend - Arm a defense boost for the next incoming attack
        - !chat - Send a text message
        - !sticker - Send a sticker
        """
        bm = self.battle_manager
        
        # Show current status
        print(f"\n--- Status ---")
        print(f"  Special Attack boosts: {bm.special_attack_uses}")
        print(f"  Special Defense boosts: {bm.special_defense_uses}")
        
        if bm.defense_boost_armed:
            print("  [Defense boost ARMED for next incoming attack]")
        
        # Show commands
        print("\nCommands:")
        print("  !attack  - Attack the opponent")
        print("  !defend  - Arm defense boost for next attack")
        print("  !chat    - Send a text message")
        print("  !sticker - Send a sticker")
        
        # Get user input
        user_input = input("\nEnter command: ")
        command = user_input.strip().lower()
        
        # Handle commands
        if command == "!attack":
            self.perform_attack()
        
        elif command == "!defend":
            # Can only arm defense when waiting for opponent
            if bm.is_my_turn:
                print("You can only arm defense boost when waiting for opponent's attack.")
            else:
                bm.arm_defense_boost()
        
        elif command == "!chat":
            text = input("Type your message: ")
            self.send_chat_message(text)
            print("Message sent!")
        
        elif command == "!sticker":
            sticker = input("Enter sticker data (Base64): ")
            self.send_sticker_message(sticker)
            print("Sticker sent!")
        
        else:
            print(f"Unknown command: {command}")
