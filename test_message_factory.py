"""
Test the MessageFactory to ensure all messages are RFC-compliant.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from protocol.message_factory import MessageFactory
from protocol.constants import MessageType, ContentType


def test_handshake_messages():
    """Test handshake message creation."""
    print("\n=== Testing Handshake Messages ===")
    
    # HANDSHAKE_REQUEST
    msg = MessageFactory.handshake_request()
    assert msg["message_type"] == MessageType.HANDSHAKE_REQUEST
    assert len(msg) == 1  # Only message_type
    print(f"HANDSHAKE_REQUEST: {msg} ✓")
    
    # HANDSHAKE_RESPONSE
    msg = MessageFactory.handshake_response(12345)
    assert msg["message_type"] == MessageType.HANDSHAKE_RESPONSE
    assert msg["seed"] == 12345
    print(f"HANDSHAKE_RESPONSE: {msg} ✓")
    
    # SPECTATOR_REQUEST
    msg = MessageFactory.spectator_request()
    assert msg["message_type"] == MessageType.SPECTATOR_REQUEST
    assert len(msg) == 1
    print(f"SPECTATOR_REQUEST: {msg} ✓")
    
    print("✓ Handshake messages test passed!")


def test_battle_setup():
    """Test BATTLE_SETUP message creation."""
    print("\n=== Testing BATTLE_SETUP ===")
    
    msg = MessageFactory.battle_setup(
        communication_mode="P2P",
        pokemon_name="Pikachu",
        special_attack_uses=5,
        special_defense_uses=5
    )
    
    assert msg["message_type"] == MessageType.BATTLE_SETUP
    assert msg["communication_mode"] == "P2P"
    assert msg["pokemon_name"] == "Pikachu"
    assert msg["stat_boosts"]["special_attack_uses"] == 5
    assert msg["stat_boosts"]["special_defense_uses"] == 5
    
    print(f"BATTLE_SETUP: {msg} ✓")
    print("✓ BATTLE_SETUP test passed!")


def test_attack_messages():
    """Test attack-related messages."""
    print("\n=== Testing Attack Messages ===")
    
    # ATTACK_ANNOUNCE - per RFC: only message_type and move_name
    msg = MessageFactory.attack_announce("Thunderbolt")
    assert msg["message_type"] == MessageType.ATTACK_ANNOUNCE
    assert msg["move_name"] == "Thunderbolt"
    assert "attacker_name" not in msg  # Per RFC
    assert "defender_name" not in msg  # Per RFC
    assert len(msg) == 2  # Only message_type and move_name
    print(f"ATTACK_ANNOUNCE: {msg} ✓")
    
    # DEFENSE_ANNOUNCE - per RFC: only message_type
    msg = MessageFactory.defense_announce()
    assert msg["message_type"] == MessageType.DEFENSE_ANNOUNCE
    assert len(msg) == 1
    print(f"DEFENSE_ANNOUNCE: {msg} ✓")
    
    print("✓ Attack messages test passed!")


def test_calculation_messages():
    """Test calculation-related messages."""
    print("\n=== Testing Calculation Messages ===")
    
    # CALCULATION_REPORT - per RFC
    msg = MessageFactory.calculation_report(
        attacker_name="Pikachu",
        move_used="Thunderbolt",
        attacker_remaining_health=90,
        damage_dealt=80,
        defender_hp_remaining=20,
        status_message="Pikachu used Thunderbolt! It was super effective!"
    )
    assert msg["message_type"] == MessageType.CALCULATION_REPORT
    assert msg["attacker"] == "Pikachu"
    assert msg["move_used"] == "Thunderbolt"
    assert msg["remaining_health"] == "90"
    assert msg["damage_dealt"] == "80"
    assert msg["defender_hp_remaining"] == "20"
    assert msg["status_message"] == "Pikachu used Thunderbolt! It was super effective!"
    print(f"CALCULATION_REPORT: {msg} ✓")
    
    # CALCULATION_CONFIRM - per RFC: only message_type
    msg = MessageFactory.calculation_confirm()
    assert msg["message_type"] == MessageType.CALCULATION_CONFIRM
    assert len(msg) == 1
    print(f"CALCULATION_CONFIRM: {msg} ✓")
    
    # RESOLUTION_REQUEST - per RFC
    msg = MessageFactory.resolution_request(
        attacker_name="Pikachu",
        move_used="Thunderbolt",
        damage_dealt=80,
        defender_hp_remaining=20
    )
    assert msg["message_type"] == MessageType.RESOLUTION_REQUEST
    assert msg["attacker"] == "Pikachu"
    assert msg["move_used"] == "Thunderbolt"
    assert msg["damage_dealt"] == "80"
    assert msg["defender_hp_remaining"] == "20"
    print(f"RESOLUTION_REQUEST: {msg} ✓")
    
    print("✓ Calculation messages test passed!")


def test_game_over():
    """Test GAME_OVER message."""
    print("\n=== Testing GAME_OVER ===")
    
    msg = MessageFactory.game_over("Pikachu", "Charmander")
    assert msg["message_type"] == MessageType.GAME_OVER
    assert msg["winner"] == "Pikachu"
    assert msg["loser"] == "Charmander"
    
    print(f"GAME_OVER: {msg} ✓")
    print("✓ GAME_OVER test passed!")


def test_chat_messages():
    """Test chat messages."""
    print("\n=== Testing Chat Messages ===")
    
    # TEXT message
    msg = MessageFactory.chat_text("Player1", "Good luck!")
    assert msg["message_type"] == MessageType.CHAT_MESSAGE
    assert msg["sender_name"] == "Player1"
    assert msg["content_type"] == ContentType.TEXT
    assert msg["message_text"] == "Good luck!"
    print(f"CHAT_MESSAGE (TEXT): {msg} ✓")
    
    # STICKER message
    msg = MessageFactory.chat_sticker("Player2", "base64data...")
    assert msg["message_type"] == MessageType.CHAT_MESSAGE
    assert msg["sender_name"] == "Player2"
    assert msg["content_type"] == ContentType.STICKER
    assert msg["sticker_data"] == "base64data..."
    print(f"CHAT_MESSAGE (STICKER): {msg} ✓")
    
    print("✓ Chat messages test passed!")


def test_ack():
    """Test ACK message."""
    print("\n=== Testing ACK ===")
    
    msg = MessageFactory.ack(5)
    assert msg["message_type"] == MessageType.ACK
    assert msg["ack_number"] == 5
    
    print(f"ACK: {msg} ✓")
    print("✓ ACK test passed!")


def main():
    """Run all MessageFactory tests."""
    print("=" * 60)
    print("MessageFactory RFC Compliance Tests")
    print("=" * 60)
    
    try:
        test_handshake_messages()
        test_battle_setup()
        test_attack_messages()
        test_calculation_messages()
        test_game_over()
        test_chat_messages()
        test_ack()
        
        print("\n" + "=" * 60)
        print("ALL MESSAGE FACTORY TESTS PASSED!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

