"""
Peers module - contains peer implementations for the battle protocol.
"""
from peers.base_peer import BasePeer
from peers.host import Host
from peers.joiner import Joiner

# Backwards compatibility aliases
host = Host
joiner = Joiner

__all__ = ["BasePeer", "Host", "Joiner", "host", "joiner"]

