"""
The Joiner peer - connects to a host and battles.
Joiner receives the seed and goes second.
"""

import threading
import time

from peers.base_peer import BasePeer
from protocol.messages import encode_message, decode_message
from protocol.message_factory import MessageFactory


class Joiner(BasePeer):
    """The joiner that connects to a host."""

    def __init__(self, pokemon, db, comm_mode: str):
        """Sets up the joiner."""
        super().__init__(pokemon, db, comm_mode, is_host=False)
        self.seed = None

    def start(self, host_ip: str, host_port: int):
        """Connects to a host and starts the battle."""
        
        # bind socket
        if self.comm_mode == "P2P":
            self.sock.bind(("", 0))
        else:
            self.sock.bind(("0.0.0.0", host_port))
        
        # get name
        self.name = input("Enter your name: ")
        
        # start listener
        self.running = True
        listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
        listener_thread.start()
        
        # send handshake
        self._send_handshake(host_ip, host_port)
        
        print("[JOINER] Handshake sent. Waiting for Host to accept...")
        print("(If the Host doesn't respond, press Ctrl+C to exit)")
        
        # wait for seed
        while self.seed is None:
            time.sleep(0.5)
        
        print("[JOINER] Connected! Received seed from Host.")
        
        # send battle setup
        self._send_battle_setup()
        
        # start chat loop
        print("\n--- Battle Ready! ---")
        print("Waiting for Host to make the first move...")
        while True:
            self.chat()

    def _send_handshake(self, host_ip: str, host_port: int):
        """Sends handshake request to host."""
        
        self.remote_addr = (host_ip, host_port)
        
        handshake_request = MessageFactory.handshake_request()
        encoded_message = encode_message(handshake_request)
        self.sock.sendto(encoded_message.encode("utf-8"), self.remote_addr)
        
        print(f"[JOINER] Sent HANDSHAKE_REQUEST to {host_ip}:{host_port}")

    def _send_battle_setup(self):
        """Sends our pokemon info to host."""
        
        battle_setup = MessageFactory.battle_setup(
            communication_mode=self.comm_mode,
            pokemon_name=self.pokemon.name,
        )
        
        print(f"[JOINER] Sending BATTLE_SETUP: {self.pokemon.name}")
        self.reliability.send_with_ack(battle_setup, self.remote_addr)

    def process_message(self, message: dict, sender_address: tuple):
        """Processes messages with joiner-specific handling."""
        
        # get seed from handshake response
        if "seed" in message and self.seed is None:
            seed_value = int(message["seed"])
            self.seed = seed_value
            self.initialize_rng(seed_value)
        
        # use parent handler
        super().process_message(message, sender_address)


# for backwards compatibility
joiner = Joiner
