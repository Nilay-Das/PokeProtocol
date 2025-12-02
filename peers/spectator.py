"""
The Spectator peer - watches battles without participating.
Can send chat messages but cant attack.
"""

import time
import threading

from peers.base_peer import BasePeer
from protocol.messages import encode_message
from protocol.constants import MessageType, ContentType
from protocol.message_factory import MessageFactory


class Spectator(BasePeer):
    """A spectator that watches battles."""

    def __init__(self):
        """Sets up the spectator."""
        super().__init__(
            pokemon=None,
            db=None,
            comm_mode="P2P",
            is_host=False
        )
        self.connected = False

    def start(self, host_ip: str, host_port: int):
        """Connects to a battle as a spectator."""
        
        # bind socket
        self.sock.bind(("", 0))
        
        # get name
        self.name = input("Enter your spectator name: ")
        
        # start listener
        self.running = True
        self.listening = True
        
        listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
        listener_thread.start()
        
        # send spectator request
        self._send_spectator_request(host_ip, host_port)
        print("[SPECTATOR] Request sent. Waiting for Host to accept...")
        
        # wait for connection
        while not self.connected:
            time.sleep(0.1)
        
        print("\n--- Connected as Spectator ---")
        print("You will see battle updates below.")
        print("Type any message and press Enter to chat.\n")
        
        # chat loop
        while self.listening:
            self.chat()

    def _send_spectator_request(self, host_ip: str, host_port: int):
        """Sends spectator request to host."""
        
        self.remote_addr = (host_ip, int(host_port))
        
        spectator_request = MessageFactory.spectator_request()
        encoded_message = encode_message(spectator_request)
        self.sock.sendto(encoded_message.encode("utf-8"), self.remote_addr)

    def process_message(self, message: dict, sender_address: tuple):
        """Processes messages for display."""
        
        message_type = message.get("message_type")
        
        # connection confirmed
        if message_type == MessageType.HANDSHAKE_RESPONSE:
            self.connected = True
            return
        
        # chat
        if message_type == MessageType.CHAT_MESSAGE:
            self._display_chat_message(message)
            return
        
        # battle setup
        if message_type == MessageType.BATTLE_SETUP:
            pokemon_name = message.get("pokemon_name", "Unknown")
            print(f"\n[SETUP] A player has selected {pokemon_name}!")
            return
        
        # attack
        if message_type == MessageType.ATTACK_ANNOUNCE:
            move_name = message.get("move_name", "Unknown")
            print(f"\n[ATTACK] Move used: {move_name}")
            return
        
        # damage
        if message_type == MessageType.CALCULATION_REPORT:
            self._display_damage_report(message)
            return
        
        # game over
        if message_type == MessageType.GAME_OVER:
            self._display_game_over(message)
            return
        
        # track acks
        if "ack_number" in message:
            self.ack = int(message["ack_number"])

    def _display_chat_message(self, message: dict):
        """Shows a chat message."""
        
        sender_name = message.get("sender_name", "Unknown")
        content_type = message.get("content_type", ContentType.TEXT)
        
        if content_type == ContentType.TEXT:
            message_text = message.get("message_text", "")
            print(f"\n[Chat] {sender_name}: {message_text}")
        elif content_type == ContentType.STICKER:
            print(f"\n[Chat] {sender_name} sent a sticker!")

    def _display_damage_report(self, message: dict):
        """Shows damage info."""
        
        status_message = message.get("status_message", "")
        if status_message:
            print(f"\n[BATTLE] {status_message}")
        
        damage_dealt = message.get("damage_dealt", "?")
        defender_hp = message.get("defender_hp_remaining", "?")
        
        print(f"[DAMAGE] Defender took {damage_dealt} damage (HP remaining: {defender_hp})")

    def _display_game_over(self, message: dict):
        """Shows game over message."""
        
        winner = message.get("winner", "Unknown")
        loser = message.get("loser", "Unknown")
        
        print("\n" + "=" * 40)
        print("GAME OVER!")
        print(f"{winner} defeated {loser}!")
        print("=" * 40 + "\n")

    def chat(self):
        """Spectator chat - just text messages."""
        
        try:
            user_input = input()
        except EOFError:
            return
        
        if not user_input.strip():
            return
        
        chat_message = MessageFactory.chat_text(self.name, user_input)
        self.reliability.send_with_ack(chat_message, self.remote_addr)


# for backwards compatibility
spectator = Spectator
