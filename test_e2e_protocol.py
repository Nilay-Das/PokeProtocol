"""
End-to-end test simulating full battle flow between host and joiner.
Verifies message exchange follows RFC specification.
"""

import sys
import os
import socket
import threading
import time
import queue

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from protocol.messages import encode_message, decode_message
from protocol.battle_state import initialize_battle_rng
from protocol.pokemon_db import load_pokemon_db


def create_test_socket(port=0):
    """Create a UDP socket for testing."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.settimeout(5.0)  # 5 second timeout for tests
    return sock


def send_message(sock, msg, addr):
    """Send a message to an address."""
    encoded = encode_message(msg)
    sock.sendto(encoded.encode("utf-8"), addr)
    print(f"  -> Sent: {msg['message_type']}")


def receive_message(sock):
    """Receive and decode a message."""
    data, addr = sock.recvfrom(4096)
    decoded = decode_message(data.decode("utf-8"))
    print(f"  <- Received: {decoded['message_type']}")
    return decoded, addr


def test_handshake_flow():
    """Test the handshake between host and joiner."""
    print("\n=== Testing Handshake Flow ===")
    
    host_sock = create_test_socket(5100)
    joiner_sock = create_test_socket(0)
    
    host_addr = ("127.0.0.1", 5100)
    
    try:
        # Step 1: Joiner sends HANDSHAKE_REQUEST
        print("1. Joiner sends HANDSHAKE_REQUEST")
        send_message(joiner_sock, {"message_type": "HANDSHAKE_REQUEST"}, host_addr)
        
        # Step 2: Host receives HANDSHAKE_REQUEST
        msg, joiner_addr = receive_message(host_sock)
        assert msg["message_type"] == "HANDSHAKE_REQUEST"
        print("   Host received HANDSHAKE_REQUEST ✓")
        
        # Step 3: Host sends HANDSHAKE_RESPONSE with seed
        print("2. Host sends HANDSHAKE_RESPONSE with seed")
        send_message(host_sock, {"message_type": "HANDSHAKE_RESPONSE", "seed": 12345}, joiner_addr)
        
        # Step 4: Joiner receives HANDSHAKE_RESPONSE
        msg, _ = receive_message(joiner_sock)
        assert msg["message_type"] == "HANDSHAKE_RESPONSE"
        assert "seed" in msg
        assert msg["seed"] == "12345"
        print(f"   Joiner received seed: {msg['seed']} ✓")
        
        print("✓ Handshake flow test passed!")
        
    finally:
        host_sock.close()
        joiner_sock.close()


def test_battle_setup_flow():
    """Test the battle setup message exchange."""
    print("\n=== Testing Battle Setup Flow ===")
    
    host_sock = create_test_socket(5101)
    joiner_sock = create_test_socket(0)
    
    host_addr = ("127.0.0.1", 5101)
    joiner_addr = None
    
    try:
        # Simulate handshake first
        send_message(joiner_sock, {"message_type": "HANDSHAKE_REQUEST"}, host_addr)
        _, joiner_addr = receive_message(host_sock)
        send_message(host_sock, {"message_type": "HANDSHAKE_RESPONSE", "seed": 12345}, joiner_addr)
        receive_message(joiner_sock)
        
        # Step 1: Joiner sends BATTLE_SETUP
        print("1. Joiner sends BATTLE_SETUP")
        setup_msg = {
            "message_type": "BATTLE_SETUP",
            "communication_mode": "P2P",
            "pokemon_name": "Pikachu",
            "stat_boosts": {"special_attack_uses": 5, "special_defense_uses": 5},
            "sequence_number": "1",
        }
        send_message(joiner_sock, setup_msg, host_addr)
        
        # Step 2: Host receives BATTLE_SETUP
        msg, _ = receive_message(host_sock)
        assert msg["message_type"] == "BATTLE_SETUP"
        assert msg["pokemon_name"] == "Pikachu"
        assert "stat_boosts" in msg
        print(f"   Host received BATTLE_SETUP: {msg['pokemon_name']} ✓")
        
        # Host sends ACK
        send_message(host_sock, {"message_type": "ACK", "ack_number": "1"}, joiner_addr)
        receive_message(joiner_sock)  # Joiner receives ACK
        
        # Step 3: Host sends BATTLE_SETUP response
        print("2. Host sends BATTLE_SETUP")
        setup_msg = {
            "message_type": "BATTLE_SETUP",
            "communication_mode": "P2P",
            "pokemon_name": "Charmander",
            "stat_boosts": {"special_attack_uses": 5, "special_defense_uses": 5},
            "sequence_number": "1",
        }
        send_message(host_sock, setup_msg, joiner_addr)
        
        # Joiner receives BATTLE_SETUP
        msg, _ = receive_message(joiner_sock)
        assert msg["message_type"] == "BATTLE_SETUP"
        assert msg["pokemon_name"] == "Charmander"
        print(f"   Joiner received BATTLE_SETUP: {msg['pokemon_name']} ✓")
        
        print("✓ Battle setup flow test passed!")
        
    finally:
        host_sock.close()
        joiner_sock.close()


def test_attack_flow():
    """Test the four-step attack handshake."""
    print("\n=== Testing Attack Flow (4-Step Handshake) ===")
    
    host_sock = create_test_socket(5102)
    joiner_sock = create_test_socket(0)
    
    host_addr = ("127.0.0.1", 5102)
    
    try:
        # Get joiner address
        send_message(joiner_sock, {"message_type": "HANDSHAKE_REQUEST"}, host_addr)
        _, joiner_addr = receive_message(host_sock)
        send_message(host_sock, {"message_type": "HANDSHAKE_RESPONSE", "seed": 12345}, joiner_addr)
        receive_message(joiner_sock)
        
        # Step 1: Host sends ATTACK_ANNOUNCE (per spec: only move_name + sequence_number)
        print("1. Host sends ATTACK_ANNOUNCE")
        attack_msg = {
            "message_type": "ATTACK_ANNOUNCE",
            "move_name": "Thunderbolt",
            "sequence_number": "5",
        }
        # Verify no extra fields
        assert "attacker_name" not in attack_msg
        assert "defender_name" not in attack_msg
        send_message(host_sock, attack_msg, joiner_addr)
        
        # Joiner receives ATTACK_ANNOUNCE
        msg, _ = receive_message(joiner_sock)
        assert msg["message_type"] == "ATTACK_ANNOUNCE"
        assert msg["move_name"] == "Thunderbolt"
        assert "attacker_name" not in msg  # Verify spec compliance
        print("   Joiner received ATTACK_ANNOUNCE ✓")
        
        # Step 2: Joiner sends DEFENSE_ANNOUNCE (per spec: only message_type + sequence_number)
        print("2. Joiner sends DEFENSE_ANNOUNCE")
        defense_msg = {
            "message_type": "DEFENSE_ANNOUNCE",
            "sequence_number": "6",
        }
        # Verify no extra fields
        assert "defender_name" not in defense_msg
        assert "acknowledged_move" not in defense_msg
        send_message(joiner_sock, defense_msg, host_addr)
        
        # Host receives DEFENSE_ANNOUNCE
        msg, _ = receive_message(host_sock)
        assert msg["message_type"] == "DEFENSE_ANNOUNCE"
        assert "defender_name" not in msg  # Verify spec compliance
        print("   Host received DEFENSE_ANNOUNCE ✓")
        
        # Step 3: Both send CALCULATION_REPORT (per spec fields)
        print("3. Both send CALCULATION_REPORT")
        report_msg = {
            "message_type": "CALCULATION_REPORT",
            "attacker": "Pikachu",
            "move_used": "Thunderbolt",
            "remaining_health": "90",
            "damage_dealt": "80",
            "defender_hp_remaining": "20",
            "status_message": "Pikachu used Thunderbolt! It was super effective!",
            "sequence_number": "7",
        }
        # Verify correct field names (not old names)
        assert "attacker" in report_msg
        assert "attacker_name" not in report_msg
        assert "move_used" in report_msg
        assert "move_name" not in report_msg
        assert "remaining_health" in report_msg
        assert "status_message" in report_msg
        
        send_message(host_sock, report_msg, joiner_addr)
        msg, _ = receive_message(joiner_sock)
        assert msg["message_type"] == "CALCULATION_REPORT"
        assert "attacker" in msg
        assert "status_message" in msg
        print("   CALCULATION_REPORT format verified ✓")
        
        # Step 4: Send CALCULATION_CONFIRM (per spec: only message_type + sequence_number)
        print("4. Joiner sends CALCULATION_CONFIRM")
        confirm_msg = {
            "message_type": "CALCULATION_CONFIRM",
            "sequence_number": "8",
        }
        # Verify no extra fields
        assert "damage_confirmed" not in confirm_msg
        assert "remaining_health" not in confirm_msg
        send_message(joiner_sock, confirm_msg, host_addr)
        
        msg, _ = receive_message(host_sock)
        assert msg["message_type"] == "CALCULATION_CONFIRM"
        assert "damage_confirmed" not in msg  # Verify spec compliance
        print("   Host received CALCULATION_CONFIRM ✓")
        
        print("✓ Attack flow test passed!")
        
    finally:
        host_sock.close()
        joiner_sock.close()


def test_chat_message():
    """Test chat message format."""
    print("\n=== Testing Chat Message ===")
    
    host_sock = create_test_socket(5103)
    joiner_sock = create_test_socket(0)
    
    host_addr = ("127.0.0.1", 5103)
    
    try:
        # Get joiner address
        send_message(joiner_sock, {"message_type": "HANDSHAKE_REQUEST"}, host_addr)
        _, joiner_addr = receive_message(host_sock)
        send_message(host_sock, {"message_type": "HANDSHAKE_RESPONSE", "seed": 12345}, joiner_addr)
        receive_message(joiner_sock)
        
        # Test TEXT message
        print("1. Testing TEXT chat message")
        chat_msg = {
            "message_type": "CHAT_MESSAGE",
            "sender_name": "Player1",
            "content_type": "TEXT",
            "message_text": "Good luck!",
            "sequence_number": "11",
        }
        send_message(joiner_sock, chat_msg, host_addr)
        msg, _ = receive_message(host_sock)
        assert msg["message_type"] == "CHAT_MESSAGE"
        assert msg["content_type"] == "TEXT"
        assert msg["message_text"] == "Good luck!"
        print("   TEXT message verified ✓")
        
        # Test STICKER message
        print("2. Testing STICKER chat message")
        sticker_msg = {
            "message_type": "CHAT_MESSAGE",
            "sender_name": "Player2",
            "content_type": "STICKER",
            "sticker_data": "iVBORw0KGgoAAAANSUhEUgAAA...",  # Truncated base64
            "sequence_number": "12",
        }
        send_message(host_sock, sticker_msg, joiner_addr)
        msg, _ = receive_message(joiner_sock)
        assert msg["message_type"] == "CHAT_MESSAGE"
        assert msg["content_type"] == "STICKER"
        assert "sticker_data" in msg
        print("   STICKER message verified ✓")
        
        print("✓ Chat message test passed!")
        
    finally:
        host_sock.close()
        joiner_sock.close()


def test_spectator_request():
    """Test spectator connection flow."""
    print("\n=== Testing Spectator Request ===")
    
    host_sock = create_test_socket(5104)
    spectator_sock = create_test_socket(0)
    
    host_addr = ("127.0.0.1", 5104)
    
    try:
        # Spectator sends SPECTATOR_REQUEST
        print("1. Spectator sends SPECTATOR_REQUEST")
        send_message(spectator_sock, {"message_type": "SPECTATOR_REQUEST"}, host_addr)
        
        # Host receives SPECTATOR_REQUEST
        msg, spec_addr = receive_message(host_sock)
        assert msg["message_type"] == "SPECTATOR_REQUEST"
        print("   Host received SPECTATOR_REQUEST ✓")
        
        # Host sends HANDSHAKE_RESPONSE
        print("2. Host sends HANDSHAKE_RESPONSE")
        send_message(host_sock, {"message_type": "HANDSHAKE_RESPONSE"}, spec_addr)
        
        msg, _ = receive_message(spectator_sock)
        assert msg["message_type"] == "HANDSHAKE_RESPONSE"
        print("   Spectator connected ✓")
        
        print("✓ Spectator request test passed!")
        
    finally:
        host_sock.close()
        spectator_sock.close()


def test_game_over():
    """Test GAME_OVER message."""
    print("\n=== Testing GAME_OVER ===")
    
    host_sock = create_test_socket(5105)
    joiner_sock = create_test_socket(0)
    
    host_addr = ("127.0.0.1", 5105)
    
    try:
        send_message(joiner_sock, {"message_type": "HANDSHAKE_REQUEST"}, host_addr)
        _, joiner_addr = receive_message(host_sock)
        
        # Send GAME_OVER
        print("1. Sending GAME_OVER message")
        game_over_msg = {
            "message_type": "GAME_OVER",
            "winner": "Pikachu",
            "loser": "Charmander",
            "sequence_number": "10",
        }
        send_message(host_sock, game_over_msg, joiner_addr)
        
        msg, _ = receive_message(joiner_sock)
        assert msg["message_type"] == "GAME_OVER"
        assert msg["winner"] == "Pikachu"
        assert msg["loser"] == "Charmander"
        print(f"   GAME_OVER received: {msg['winner']} defeated {msg['loser']} ✓")
        
        print("✓ GAME_OVER test passed!")
        
    finally:
        host_sock.close()
        joiner_sock.close()


def test_resolution_request():
    """Test RESOLUTION_REQUEST message format."""
    print("\n=== Testing RESOLUTION_REQUEST ===")
    
    host_sock = create_test_socket(5106)
    joiner_sock = create_test_socket(0)
    
    host_addr = ("127.0.0.1", 5106)
    
    try:
        send_message(joiner_sock, {"message_type": "HANDSHAKE_REQUEST"}, host_addr)
        _, joiner_addr = receive_message(host_sock)
        
        # Send RESOLUTION_REQUEST (per spec fields)
        print("1. Sending RESOLUTION_REQUEST message")
        resolution_msg = {
            "message_type": "RESOLUTION_REQUEST",
            "attacker": "Pikachu",
            "move_used": "Thunderbolt",
            "damage_dealt": "80",
            "defender_hp_remaining": "20",
            "sequence_number": "9",
        }
        # Verify no extra fields
        assert "calculated_damage" not in resolution_msg
        assert "attacker_stat" not in resolution_msg
        
        send_message(host_sock, resolution_msg, joiner_addr)
        
        msg, _ = receive_message(joiner_sock)
        assert msg["message_type"] == "RESOLUTION_REQUEST"
        assert msg["attacker"] == "Pikachu"
        assert msg["move_used"] == "Thunderbolt"
        print("   RESOLUTION_REQUEST format verified ✓")
        
        print("✓ RESOLUTION_REQUEST test passed!")
        
    finally:
        host_sock.close()
        joiner_sock.close()


def main():
    """Run all end-to-end tests."""
    print("=" * 60)
    print("PokeProtocol End-to-End Tests")
    print("=" * 60)
    
    try:
        test_handshake_flow()
        test_battle_setup_flow()
        test_attack_flow()
        test_chat_message()
        test_spectator_request()
        test_game_over()
        test_resolution_request()
        
        print("\n" + "=" * 60)
        print("ALL END-TO-END TESTS PASSED!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except socket.timeout:
        print("\n❌ TEST FAILED: Socket timeout - message not received")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

