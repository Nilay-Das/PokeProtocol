"""
=============================================================================
SPECTATOR PEER - Watching the Battle
=============================================================================

WHAT IS THIS FILE?
------------------
This file implements the Spectator peer. The Spectator is like a viewer that:
1. Connects to the Host
2. Receives battle updates (attacks, damage, game over)
3. Can send chat messages
4. CANNOT participate in the battle

WHAT DOES THE SPECTATOR DO?
---------------------------
1. CONNECT PHASE:
   - Send SPECTATOR_REQUEST to the Host
   - Wait for HANDSHAKE_RESPONSE (confirmation)

2. WATCH PHASE:
   - Display BATTLE_SETUP messages (who chose what Pokemon)
   - Display ATTACK_ANNOUNCE messages (what moves are used)
   - Display CALCULATION_REPORT messages (damage dealt)
   - Display GAME_OVER message (who won)
   - Can send chat messages at any time

SPECTATOR VS HOST/JOINER
------------------------
- Spectators DO NOT have a Pokemon
- Spectators DO NOT take turns
- Spectators DO NOT send or receive battle messages
- Spectators CAN send chat messages
- Spectators just WATCH and DISPLAY battle information

=============================================================================
"""

import time
import threading

from peers.base_peer import BasePeer
from protocol.messages import encode_message
from protocol.constants import MessageType, ContentType
from protocol.message_factory import MessageFactory


class Spectator(BasePeer):
    """
    A spectator peer that watches a battle without participating.
    
    Spectators:
    - Connect to the Host like Joiners do
    - Receive all battle messages from the Host
    - Can send chat messages
    - Cannot attack or influence the battle
    
    Inherits from BasePeer but uses minimal functionality.
    """

    def __init__(self):
        """
        Initialize the Spectator peer.
        
        Spectators don't need:
        - A Pokemon (they don't battle)
        - A database (they don't look up Pokemon)
        - Host status (they're always clients)
        """
        # Initialize with no Pokemon - spectators just watch
        super().__init__(
            pokemon=None,
            db=None,
            comm_mode="P2P",
            is_host=False
        )
        
        # Are we connected to the Host?
        self.connected = False

    def start(self, host_ip: str, host_port: int):
        """
        Start the Spectator and connect to a battle.
        
        This function:
        1. Binds our socket to a local port
        2. Sends a SPECTATOR_REQUEST to the Host
        3. Waits for the Host to accept us
        4. Displays battle updates as they happen
        
        Args:
            host_ip: The IP address of the Host
            host_port: The port number the Host is listening on
        """
        # Step 1: Bind our socket to a free port
        self.sock.bind(("", 0))
        
        # Step 2: Get our display name
        self.name = input("Enter your spectator name: ")
        
        # Step 3: Start the listener loop
        self.running = True
        self.listening = True
        
        listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
        listener_thread.start()
        
        # Step 4: Send SPECTATOR_REQUEST to the Host
        self._send_spectator_request(host_ip, host_port)
        print("[SPECTATOR] Request sent. Waiting for Host to accept...")
        
        # Step 5: Wait for connection confirmation
        while not self.connected:
            time.sleep(0.1)
        
        print("\n--- Connected as Spectator ---")
        print("You will see battle updates below.")
        print("Type any message and press Enter to chat.\n")
        
        # Step 6: Main loop - handle chat input
        while self.listening:
            self.chat()

    def _send_spectator_request(self, host_ip: str, host_port: int):
        """
        Send a SPECTATOR_REQUEST to the Host.
        
        This asks the Host if we can watch the battle.
        
        Args:
            host_ip: The IP address of the Host
            host_port: The port number
        """
        # Store the Host's address
        self.remote_addr = (host_ip, int(host_port))
        
        # Create and send the request
        spectator_request = MessageFactory.spectator_request()
        encoded_message = encode_message(spectator_request)
        self.sock.sendto(encoded_message.encode("utf-8"), self.remote_addr)

    def process_message(self, message: dict, sender_address: tuple):
        """
        Process received messages for display.
        
        Spectators don't participate in battle logic.
        We just display the messages in a nice format.
        
        Args:
            message: The decoded message dictionary
            sender_address: The (IP, port) of who sent it
        """
        message_type = message.get("message_type")
        
        # Handle connection confirmation
        if message_type == MessageType.HANDSHAKE_RESPONSE:
            self.connected = True
            return
        
        # Handle chat messages
        if message_type == MessageType.CHAT_MESSAGE:
            self._display_chat_message(message)
            return
        
        # Handle battle setup
        if message_type == MessageType.BATTLE_SETUP:
            pokemon_name = message.get("pokemon_name", "Unknown")
            print(f"\n[SETUP] A player has selected {pokemon_name}!")
            return
        
        # Handle attack announcements
        if message_type == MessageType.ATTACK_ANNOUNCE:
            move_name = message.get("move_name", "Unknown")
            print(f"\n[ATTACK] Move used: {move_name}")
            return
        
        # Handle damage reports
        if message_type == MessageType.CALCULATION_REPORT:
            self._display_damage_report(message)
            return
        
        # Handle game over
        if message_type == MessageType.GAME_OVER:
            self._display_game_over(message)
            return
        
        # Track ACK numbers (inherited behavior)
        if "ack_number" in message:
            self.ack = int(message["ack_number"])

    def _display_chat_message(self, message: dict):
        """
        Display a chat message in a nice format.
        
        Args:
            message: The CHAT_MESSAGE dictionary
        """
        sender_name = message.get("sender_name", "Unknown")
        content_type = message.get("content_type", ContentType.TEXT)
        
        if content_type == ContentType.TEXT:
            message_text = message.get("message_text", "")
            print(f"\n[Chat] {sender_name}: {message_text}")
        elif content_type == ContentType.STICKER:
            print(f"\n[Chat] {sender_name} sent a sticker!")

    def _display_damage_report(self, message: dict):
        """
        Display a damage report in a nice format.
        
        Args:
            message: The CALCULATION_REPORT dictionary
        """
        # Get the status message (e.g., "Pikachu used Thunderbolt! It was super effective!")
        status_message = message.get("status_message", "")
        if status_message:
            print(f"\n[BATTLE] {status_message}")
        
        # Get the damage details
        damage_dealt = message.get("damage_dealt", "?")
        defender_hp = message.get("defender_hp_remaining", "?")
        
        print(f"[DAMAGE] Defender took {damage_dealt} damage (HP remaining: {defender_hp})")

    def _display_game_over(self, message: dict):
        """
        Display the game over message in a nice format.
        
        Args:
            message: The GAME_OVER dictionary
        """
        winner = message.get("winner", "Unknown")
        loser = message.get("loser", "Unknown")
        
        print("\n" + "=" * 40)
        print("GAME OVER!")
        print(f"{winner} defeated {loser}!")
        print("=" * 40 + "\n")

    def chat(self):
        """
        Spectator chat interface.
        
        Spectators can only send text messages - they can't attack
        or use other commands since they're not in the battle.
        """
        try:
            # Wait for user input
            user_input = input()
        except EOFError:
            # Handle end of input (Ctrl+D)
            return
        
        # Ignore empty messages
        if not user_input.strip():
            return
        
        # Send the chat message
        chat_message = MessageFactory.chat_text(self.name, user_input)
        self.reliability.send_with_ack(chat_message, self.remote_addr)


# Alias for backwards compatibility
spectator = Spectator
