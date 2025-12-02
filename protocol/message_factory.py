"""
Helper functions for creating protocol messages.
Instead of building dictionaries by hand, use these functions.
"""

from protocol.constants import (
    MessageType,
    ContentType,
    DEFAULT_SPECIAL_ATTACK_USES,
    DEFAULT_SPECIAL_DEFENSE_USES,
)


class MessageFactory:
    """Creates all the different message types for our protocol."""

    @staticmethod
    def handshake_request() -> dict:
        """Creates a HANDSHAKE_REQUEST message."""
        return {"message_type": MessageType.HANDSHAKE_REQUEST}

    @staticmethod
    def handshake_response(seed: int) -> dict:
        """Creates a HANDSHAKE_RESPONSE with the RNG seed."""
        return {"message_type": MessageType.HANDSHAKE_RESPONSE, "seed": seed}

    @staticmethod
    def spectator_request() -> dict:
        """Creates a SPECTATOR_REQUEST message."""
        return {"message_type": MessageType.SPECTATOR_REQUEST}

    @staticmethod
    def battle_setup(
        communication_mode: str,
        pokemon_name: str,
        special_attack_uses: int = DEFAULT_SPECIAL_ATTACK_USES,
        special_defense_uses: int = DEFAULT_SPECIAL_DEFENSE_USES,
    ) -> dict:
        """Creates a BATTLE_SETUP message with pokemon info."""
        message = {
            "message_type": MessageType.BATTLE_SETUP,
            "communication_mode": communication_mode,
            "pokemon_name": pokemon_name,
            "stat_boosts": {
                "special_attack_uses": special_attack_uses,
                "special_defense_uses": special_defense_uses,
            },
        }
        return message

    @staticmethod
    def attack_announce(move_name: str) -> dict:
        """Creates an ATTACK_ANNOUNCE message."""
        return {"message_type": MessageType.ATTACK_ANNOUNCE, "move_name": move_name}

    @staticmethod
    def defense_announce() -> dict:
        """Creates a DEFENSE_ANNOUNCE message."""
        return {"message_type": MessageType.DEFENSE_ANNOUNCE}

    @staticmethod
    def calculation_report(
        attacker_name: str,
        move_used: str,
        attacker_remaining_health: int,
        damage_dealt: int,
        defender_hp_remaining: int,
        status_message: str,
    ) -> dict:
        """Creates a CALCULATION_REPORT with damage info."""
        message = {
            "message_type": MessageType.CALCULATION_REPORT,
            "attacker": attacker_name,
            "move_used": move_used,
            "remaining_health": str(attacker_remaining_health),
            "damage_dealt": str(damage_dealt),
            "defender_hp_remaining": str(defender_hp_remaining),
            "status_message": status_message,
        }
        return message

    @staticmethod
    def calculation_confirm() -> dict:
        """Creates a CALCULATION_CONFIRM message."""
        return {"message_type": MessageType.CALCULATION_CONFIRM}

    @staticmethod
    def resolution_request(
        attacker_name: str,
        move_used: str,
        damage_dealt: int,
        defender_hp_remaining: int,
    ) -> dict:
        """Creates a RESOLUTION_REQUEST when calculations dont match."""
        message = {
            "message_type": MessageType.RESOLUTION_REQUEST,
            "attacker": attacker_name,
            "move_used": move_used,
            "damage_dealt": str(damage_dealt),
            "defender_hp_remaining": str(defender_hp_remaining),
        }
        return message

    @staticmethod
    def game_over(winner_name: str, loser_name: str) -> dict:
        """Creates a GAME_OVER message."""
        return {
            "message_type": MessageType.GAME_OVER,
            "winner": winner_name,
            "loser": loser_name,
        }

    @staticmethod
    def chat_text(sender_name: str, message_text: str) -> dict:
        """Creates a text chat message."""
        message = {
            "message_type": MessageType.CHAT_MESSAGE,
            "sender_name": sender_name,
            "content_type": ContentType.TEXT,
            "message_text": message_text,
        }
        return message

    @staticmethod
    def chat_sticker(sender_name: str, sticker_data: str) -> dict:
        """Creates a sticker chat message."""
        message = {
            "message_type": MessageType.CHAT_MESSAGE,
            "sender_name": sender_name,
            "content_type": ContentType.STICKER,
            "sticker_data": sticker_data,
        }
        return message

    @staticmethod
    def ack(ack_number: int) -> dict:
        """Creates an ACK message."""
        return {"message_type": MessageType.ACK, "ack_number": ack_number}
