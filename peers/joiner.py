"""
Joiner peer implementation.
Handles connecting to host and initiating battle setup.
"""

import threading
import time

from peers.base_peer import BasePeer
from protocol.messages import encode_message, decode_message


class Joiner(BasePeer):
    """
    Joiner peer that connects to a host and participates in battle.
    Inherits common functionality from BasePeer.
    """

    def __init__(self, pokemon, db, comm_mode):
        """
        Initialize joiner peer.

        Args:
            pokemon: This peer's Pokemon
            db: Pokemon database
            comm_mode: Communication mode ("P2P" or "BROADCAST")
        """
        super().__init__(pokemon, db, comm_mode, is_host=False)

        # Joiner-specific attributes
        self.seed = None

    def start(self, host_ip, host_port):
        """
        Start the joiner and connect to host.

        Args:
            host_ip: Host IP address
            host_port: Host port number
        """
        # Bind local ephemeral port
        if self.comm_mode == "P2P":
            self.sock.bind(("", 0))
        else:
            self.sock.bind(("0.0.0.0", host_port))

        self.name = input("Name this Peer\n")

        self.running = True
        t = threading.Thread(target=self.listen_loop, daemon=True)
        t.start()

        # Send handshake request
        self.handshake(host_ip, host_port)

        print("[Joiner] Handshake sent. Waiting for Host...")
        print("If host has not sent seed please Ctrl+C to end program")

        while self.seed is None:
            time.sleep(0.5)

        # Send battle setup message
        self.send_battle_setup()

        while True:
            self.chat()

    def handshake(self, host_ip, host_port):
        """
        Send handshake request to host.

        Args:
            host_ip: Host IP address
            host_port: Host port number
        """
        self.remote_addr = (host_ip, host_port)
        handshake = encode_message({"message_type": "HANDSHAKE_REQUEST"})
        self.sock.sendto(handshake.encode("utf-8"), self.remote_addr)

    def send_battle_setup(self):
        """Send battle setup message to host."""
        msg = {
            "message_type": "BATTLE_SETUP",
            "communication_mode": self.comm_mode,
            "pokemon_name": self.pokemon.name,
            "stat_boosts": {"special_attack_uses": 5, "special_defense_uses": 5},
        }
        print(f"[Joiner] Sending BATTLE_SETUP: {msg}")
        self.reliability.send_with_ack(msg, self.remote_addr)

    def process_message(self, kv, addr):
        """
        Process messages with joiner-specific handling.

        Args:
            kv: Decoded message dictionary
            addr: Address message came from
        """
        # Handle seed from handshake response
        if "seed" in kv:
            self.seed = int(kv["seed"])

        # Use parent class for common message handling
        super().process_message(kv, addr)

    def chat(self):
        """Joiner-specific chat interface."""
        chatmsg = input("Type a message (or !attack to attack):\n")

        if chatmsg.strip() == "!attack":
            self.perform_attack()
            return

        # Normal chat message
        self.send_chat_message(chatmsg)


# Alias for backwards compatibility
joiner = Joiner
