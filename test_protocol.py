"""
Automated test to verify PokeProtocol compliance with RFC specification.
Tests message formats, state transitions, and battle flow.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from protocol.messages import encode_message, decode_message
from protocol.battle_state import (
    Pokemon,
    Move,
    BattleState,
    BattlePhase,
    calculate_damage,
    get_damage_category,
    generate_status_message,
    initialize_battle_rng,
)
from protocol.battle_manager import BattleManager


def test_message_encoding():
    """Test that messages are encoded in the correct format."""
    print("\n=== Testing Message Encoding ===")
    
    # Test HANDSHAKE_REQUEST
    msg = {"message_type": "HANDSHAKE_REQUEST"}
    encoded = encode_message(msg)
    print(f"HANDSHAKE_REQUEST:\n{encoded}\n")
    assert "message_type: HANDSHAKE_REQUEST" in encoded
    
    # Test HANDSHAKE_RESPONSE with seed
    msg = {"message_type": "HANDSHAKE_RESPONSE", "seed": 12345}
    encoded = encode_message(msg)
    print(f"HANDSHAKE_RESPONSE:\n{encoded}\n")
    assert "message_type: HANDSHAKE_RESPONSE" in encoded
    assert "seed: 12345" in encoded
    
    # Test BATTLE_SETUP
    msg = {
        "message_type": "BATTLE_SETUP",
        "communication_mode": "P2P",
        "pokemon_name": "Pikachu",
        "stat_boosts": {"special_attack_uses": 5, "special_defense_uses": 5},
    }
    encoded = encode_message(msg)
    print(f"BATTLE_SETUP:\n{encoded}\n")
    assert "message_type: BATTLE_SETUP" in encoded
    assert "pokemon_name: Pikachu" in encoded
    
    # Test ATTACK_ANNOUNCE (should only have message_type and move_name per spec)
    msg = {"message_type": "ATTACK_ANNOUNCE", "move_name": "Thunderbolt", "sequence_number": "5"}
    encoded = encode_message(msg)
    print(f"ATTACK_ANNOUNCE:\n{encoded}\n")
    assert "message_type: ATTACK_ANNOUNCE" in encoded
    assert "move_name: Thunderbolt" in encoded
    assert "attacker_name" not in encoded  # Should NOT be present per spec
    assert "defender_name" not in encoded  # Should NOT be present per spec
    
    # Test DEFENSE_ANNOUNCE (should only have message_type per spec)
    msg = {"message_type": "DEFENSE_ANNOUNCE", "sequence_number": "6"}
    encoded = encode_message(msg)
    print(f"DEFENSE_ANNOUNCE:\n{encoded}\n")
    assert "message_type: DEFENSE_ANNOUNCE" in encoded
    assert "defender_name" not in encoded  # Should NOT be present per spec
    assert "acknowledged_move" not in encoded  # Should NOT be present per spec
    
    # Test CALCULATION_REPORT (per spec fields)
    msg = {
        "message_type": "CALCULATION_REPORT",
        "attacker": "Pikachu",
        "move_used": "Thunderbolt",
        "remaining_health": "90",
        "damage_dealt": "80",
        "defender_hp_remaining": "20",
        "status_message": "Pikachu used Thunderbolt! It was super effective!",
        "sequence_number": "7",
    }
    encoded = encode_message(msg)
    print(f"CALCULATION_REPORT:\n{encoded}\n")
    assert "attacker: Pikachu" in encoded  # Correct field name
    assert "move_used: Thunderbolt" in encoded  # Correct field name
    assert "remaining_health: 90" in encoded  # Attacker's HP
    assert "status_message:" in encoded  # Status message present
    
    # Test CALCULATION_CONFIRM (should only have message_type per spec)
    msg = {"message_type": "CALCULATION_CONFIRM", "sequence_number": "8"}
    encoded = encode_message(msg)
    print(f"CALCULATION_CONFIRM:\n{encoded}\n")
    assert "message_type: CALCULATION_CONFIRM" in encoded
    assert "damage_confirmed" not in encoded  # Should NOT be present per spec
    
    # Test RESOLUTION_REQUEST (per spec fields)
    msg = {
        "message_type": "RESOLUTION_REQUEST",
        "attacker": "Pikachu",
        "move_used": "Thunderbolt",
        "damage_dealt": "80",
        "defender_hp_remaining": "20",
        "sequence_number": "9",
    }
    encoded = encode_message(msg)
    print(f"RESOLUTION_REQUEST:\n{encoded}\n")
    assert "attacker: Pikachu" in encoded
    assert "move_used: Thunderbolt" in encoded
    
    # Test GAME_OVER
    msg = {
        "message_type": "GAME_OVER",
        "winner": "Pikachu",
        "loser": "Charmander",
        "sequence_number": "10",
    }
    encoded = encode_message(msg)
    print(f"GAME_OVER:\n{encoded}\n")
    assert "message_type: GAME_OVER" in encoded
    assert "winner: Pikachu" in encoded
    assert "loser: Charmander" in encoded
    
    # Test CHAT_MESSAGE with TEXT
    msg = {
        "message_type": "CHAT_MESSAGE",
        "sender_name": "Player1",
        "content_type": "TEXT",
        "message_text": "Good luck, have fun!",
        "sequence_number": "11",
    }
    encoded = encode_message(msg)
    print(f"CHAT_MESSAGE (TEXT):\n{encoded}\n")
    assert "content_type: TEXT" in encoded
    assert "message_text: Good luck, have fun!" in encoded
    
    print("✓ All message encoding tests passed!")


def test_message_decoding():
    """Test that messages are decoded correctly."""
    print("\n=== Testing Message Decoding ===")
    
    raw = "message_type: ATTACK_ANNOUNCE\nmove_name: Thunderbolt\nsequence_number: 5"
    decoded = decode_message(raw)
    assert decoded["message_type"] == "ATTACK_ANNOUNCE"
    assert decoded["move_name"] == "Thunderbolt"
    assert decoded["sequence_number"] == "5"
    print("✓ Message decoding test passed!")


def test_battle_manager():
    """Test BattleManager functionality."""
    print("\n=== Testing BattleManager ===")
    
    # Test as host (goes first)
    bm_host = BattleManager(is_host=True)
    assert bm_host.is_my_turn == True
    assert bm_host.battle_phase is None
    
    # Test stat boosts
    assert bm_host.special_attack_uses == 5
    assert bm_host.special_defense_uses == 5
    
    # Test using special attack boost
    assert bm_host.use_special_attack() == True
    assert bm_host.special_attack_uses == 4
    assert bm_host.use_special_attack_boost == True
    assert bm_host.get_attack_multiplier() == 1.5
    
    # Test arming defense boost
    bm_host.reset_turn_state()
    assert bm_host.use_special_attack_boost == False
    
    bm_host.arm_defense_boost()
    assert bm_host.defense_boost_armed == True
    
    bm_host.consume_armed_defense_boost()
    assert bm_host.use_special_defense_boost == True
    assert bm_host.defense_boost_armed == False
    assert bm_host.special_defense_uses == 4
    assert bm_host.get_defense_multiplier() == 1.5
    
    print("✓ BattleManager tests passed!")


def test_damage_calculation():
    """Test damage calculation with boosts."""
    print("\n=== Testing Damage Calculation ===")
    
    # Create test Pokemon with higher stats to see boost differences
    attacker = Pokemon(
        name="Pikachu",
        max_hp=100,
        current_hp=100,
        attack=100,
        special_attack=100,
        physical_defense=50,
        special_defense=50,
        type1="electric",
        type2=None,
        type_multipliers={"ground": 2.0, "electric": 0.5},
        moves=["Thunderbolt", "Quick Attack"],
    )
    
    defender = Pokemon(
        name="Squirtle",
        max_hp=100,
        current_hp=100,
        attack=50,
        special_attack=50,
        physical_defense=50,
        special_defense=50,
        type1="water",
        type2=None,
        type_multipliers={"electric": 2.0, "grass": 2.0, "water": 0.5},
        moves=["Water Gun", "Tackle"],
    )
    
    state = BattleState(attacker=attacker, defender=defender)
    move = Move(name="Thunderbolt", base_power=1, category="special", move_type="electric")
    
    # Test without boosts: (100 * 2.0) / 50 = 4
    damage_no_boost = calculate_damage(state, move, attack_boost=1.0, defense_boost=1.0)
    print(f"Damage without boosts: {damage_no_boost}")
    
    # Test with attack boost (1.5x): (150 * 2.0) / 50 = 6
    damage_with_atk = calculate_damage(state, move, attack_boost=1.5, defense_boost=1.0)
    print(f"Damage with attack boost: {damage_with_atk}")
    assert damage_with_atk > damage_no_boost, f"Attack boost should increase damage: {damage_with_atk} > {damage_no_boost}"
    
    # Test with defense boost (1.5x): (100 * 2.0) / 75 = 2.67 -> 3
    damage_with_def = calculate_damage(state, move, attack_boost=1.0, defense_boost=1.5)
    print(f"Damage with defense boost: {damage_with_def}")
    assert damage_with_def < damage_no_boost, f"Defense boost should reduce damage: {damage_with_def} < {damage_no_boost}"
    
    print("✓ Damage calculation tests passed!")


def test_status_message():
    """Test status message generation."""
    print("\n=== Testing Status Message Generation ===")
    
    # Super effective
    msg = generate_status_message("Pikachu", "Thunderbolt", 2.0)
    assert "super effective" in msg
    print(f"Super effective: {msg}")
    
    # Not very effective
    msg = generate_status_message("Pikachu", "Thunderbolt", 0.5)
    assert "not very effective" in msg
    print(f"Not very effective: {msg}")
    
    # No effect
    msg = generate_status_message("Pikachu", "Thunderbolt", 0)
    assert "no effect" in msg
    print(f"No effect: {msg}")
    
    # Normal
    msg = generate_status_message("Pikachu", "Thunderbolt", 1.0)
    assert "Pikachu used Thunderbolt!" in msg
    print(f"Normal: {msg}")
    
    print("✓ Status message tests passed!")


def test_seeded_rng():
    """Test that seeded RNG works."""
    print("\n=== Testing Seeded RNG ===")
    
    # Initialize with seed
    initialize_battle_rng(12345)
    
    # Same seed should produce same results
    from protocol.battle_state import get_battle_rng
    rng1 = get_battle_rng()
    val1 = rng1.random()
    
    initialize_battle_rng(12345)
    rng2 = get_battle_rng()
    val2 = rng2.random()
    
    assert val1 == val2, "Seeded RNG should produce same results"
    print(f"RNG with seed 12345: {val1} == {val2}")
    print("✓ Seeded RNG test passed!")


def test_attack_announce_format():
    """Test that ATTACK_ANNOUNCE is created with correct format."""
    print("\n=== Testing ATTACK_ANNOUNCE Format ===")
    
    bm = BattleManager(is_host=True)
    
    attacker = Pokemon(
        name="Pikachu", max_hp=100, current_hp=100, attack=55, special_attack=50,
        physical_defense=40, special_defense=50, type1="electric", type2=None,
        type_multipliers={}, moves=["Thunderbolt"],
    )
    defender = Pokemon(
        name="Squirtle", max_hp=100, current_hp=100, attack=48, special_attack=50,
        physical_defense=65, special_defense=64, type1="water", type2=None,
        type_multipliers={}, moves=["Water Gun"],
    )
    
    attack_msg = bm.prepare_attack(attacker, defender, "Thunderbolt")
    
    # Verify only required fields are present
    assert attack_msg["message_type"] == "ATTACK_ANNOUNCE"
    assert attack_msg["move_name"] == "Thunderbolt"
    assert "attacker_name" not in attack_msg, "ATTACK_ANNOUNCE should not have attacker_name"
    assert "defender_name" not in attack_msg, "ATTACK_ANNOUNCE should not have defender_name"
    
    print(f"ATTACK_ANNOUNCE message: {attack_msg}")
    print("✓ ATTACK_ANNOUNCE format test passed!")


def main():
    """Run all tests."""
    print("=" * 60)
    print("PokeProtocol RFC Compliance Tests")
    print("=" * 60)
    
    try:
        test_message_encoding()
        test_message_decoding()
        test_battle_manager()
        test_damage_calculation()
        test_status_message()
        test_seeded_rng()
        test_attack_announce_format()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
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

