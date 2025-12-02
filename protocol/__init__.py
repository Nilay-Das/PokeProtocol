"""
Protocol module - contains battle protocol implementation.
"""

from protocol.messages import encode_message, decode_message
from protocol.reliability import ReliableChannel
from protocol.battle_state import (
    Pokemon,
    Move,
    BattleState,
    BattlePhase,
    calculate_damage,
    apply_damage,
)
from protocol.pokemon_db import load_pokemon_db
from protocol.battle_manager import BattleManager
from protocol.message_factory import MessageFactory
from protocol.constants import MessageType, ContentType, CommunicationMode

__all__ = [
    "encode_message",
    "decode_message",
    "ReliableChannel",
    "Pokemon",
    "Move",
    "BattleState",
    "BattlePhase",
    "calculate_damage",
    "apply_damage",
    "load_pokemon_db",
    "BattleManager",
    "MessageFactory",
    "MessageType",
    "ContentType",
    "CommunicationMode",
]
