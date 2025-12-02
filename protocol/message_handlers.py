"""
=============================================================================
MESSAGE HANDLERS - Processing Protocol Messages
=============================================================================

WHAT IS THIS FILE?
------------------
This file contains functions that handle incoming protocol messages.
When we receive a message, we need to:
1. Parse it (extract the data)
2. Update our game state
3. Optionally send a response

Each message type has its own handler function.


MESSAGE FLOW DIAGRAM
--------------------
Here's how messages flow during a typical attack:

    ATTACKER                              DEFENDER
        |                                     |
        |---- ATTACK_ANNOUNCE --------------->|
        |                                     | (handle_attack_announce)
        |<----------- DEFENSE_ANNOUNCE -------|
        | (handle_defense_announce)           |
        |                                     |
        |---- CALCULATION_REPORT ------------>|
        |<----------- CALCULATION_REPORT -----|
        | (handle_calculation_report)         | (handle_calculation_report)
        |                                     |
        |---- CALCULATION_CONFIRM ----------->|
        | (handle_calculation_confirm)        |
        |                                     |
        | [Turn switches to DEFENDER]         |


FUNCTION NAMING CONVENTION
--------------------------
Each function is named: handle_<message_type>

For example:
- handle_battle_setup() handles BATTLE_SETUP messages
- handle_attack_announce() handles ATTACK_ANNOUNCE messages
- etc.

=============================================================================
"""

# We need ast.literal_eval to safely parse dictionary strings
import ast

from protocol.messages import encode_message
from protocol.battle_state import (
    Move,
    BattleState,
    BattlePhase,
    calculate_damage,
    get_damage_category,
    generate_status_message,
)
from protocol.message_factory import MessageFactory
from protocol.constants import MessageType


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_role_name(is_host: bool) -> str:
    """
    Get a display name for logging based on whether we're host or joiner.
    
    Args:
        is_host: True if we're the host, False if joiner
    
    Returns:
        "HOST" or "JOINER"
    """
    if is_host:
        return "HOST"
    else:
        return "JOINER"


def parse_stat_boosts(stat_boosts_str: str) -> tuple:
    """
    Parse the stat_boosts string from a BATTLE_SETUP message.
    
    The stat_boosts field looks like:
    {'special_attack_uses': 5, 'special_defense_uses': 5}
    
    Args:
        stat_boosts_str: The stat_boosts value from the message
    
    Returns:
        Tuple of (special_attack_uses, special_defense_uses)
        Returns (5, 5) if parsing fails
    """
    try:
        # ast.literal_eval safely evaluates a string as a Python literal
        # This converts the string "{'key': value}" into an actual dictionary
        stat_boosts_dict = ast.literal_eval(stat_boosts_str)
        
        special_attack_uses = int(stat_boosts_dict.get("special_attack_uses", 5))
        special_defense_uses = int(stat_boosts_dict.get("special_defense_uses", 5))
        
        return (special_attack_uses, special_defense_uses)
    except (ValueError, SyntaxError):
        # If parsing fails, use default values
        return (5, 5)


# =============================================================================
# BATTLE_SETUP HANDLER
# =============================================================================

def handle_battle_setup(kv: dict, peer, is_host: bool = True):
    """
    Handle a BATTLE_SETUP message from the opponent.
    
    This is called when we receive the opponent's Pokemon information.
    After this, the battle can begin!
    
    What this function does:
    1. Gets the opponent's Pokemon name from the message
    2. Looks up that Pokemon in our database
    3. Stores the opponent's stat boost allocation
    4. Transitions to the WAITING_FOR_MOVE phase
    
    Args:
        kv: The decoded message dictionary containing:
            - pokemon_name: Name of opponent's Pokemon
            - communication_mode: "P2P" or "BROADCAST"
            - stat_boosts: Dictionary with special_attack_uses and special_defense_uses
        peer: The peer object (Host or Joiner)
        is_host: True if we're the host
    
    Returns:
        None (we don't send a response to BATTLE_SETUP)
    """
    role = get_role_name(is_host)
    
    # Step 1: Get the opponent's Pokemon name
    pokemon_name = kv.get("pokemon_name")
    if not pokemon_name:
        print(f"[{role}] Error: BATTLE_SETUP missing pokemon_name")
        return None
    
    # Step 2: Look up the Pokemon in our database
    # The database uses lowercase names as keys
    opponent_pokemon = peer.db.get(pokemon_name.lower())
    
    if not opponent_pokemon:
        print(f"[{role}] Error: Unknown Pokemon '{pokemon_name}'")
        return None
    
    # Store the opponent's Pokemon
    peer.opp_mon = opponent_pokemon
    print(f"[{role}] Opponent chose {opponent_pokemon.name} (HP: {opponent_pokemon.current_hp})")
    
    # Step 3: Parse and store opponent's stat boosts
    stat_boosts_str = kv.get("stat_boosts", "")
    if stat_boosts_str:
        sp_atk_uses, sp_def_uses = parse_stat_boosts(stat_boosts_str)
        peer.battle_manager.set_opponent_stat_boosts(sp_atk_uses, sp_def_uses)
    
    # Step 4: Transition to battle phase
    peer.battle_manager.battle_phase = BattlePhase.WAITING_FOR_MOVE
    print(f"[{role}] Battle setup complete! Ready to battle.")
    
    # Tell the user what to do next
    if is_host:
        print(f"[{role}] It's your turn! Type !attack to make a move.")
    else:
        print(f"[{role}] Waiting for Host's move...")
    
    return None


# =============================================================================
# ATTACK_ANNOUNCE HANDLER
# =============================================================================

def handle_attack_announce(kv: dict, peer, is_host: bool = True):
    """
    Handle an ATTACK_ANNOUNCE message - the opponent is attacking us!
    
    This is Step 1 of the attack flow from the defender's perspective.
    
    What this function does:
    1. Parse the move name from the message
    2. Store the attack information
    3. Check if we had a defense boost armed
    4. Calculate the expected damage
    5. Create DEFENSE_ANNOUNCE and CALCULATION_REPORT responses
    
    Args:
        kv: The decoded message dictionary containing:
            - move_name: Name of the move being used
        peer: The peer object
        is_host: True if we're the host
    
    Returns:
        Tuple of (defense_msg, calculation_report_msg)
        Both messages need to be sent to the opponent
    """
    role = get_role_name(is_host)
    
    # Step 1: Get the move name
    move_name = kv.get("move_name", "")
    
    # Figure out who is attacking and defending
    # Since we RECEIVED this message, the OPPONENT is attacking US
    attacker = peer.opp_mon      # Opponent's Pokemon
    defender = peer.pokemon       # Our Pokemon
    
    # Safety check
    if attacker is None or defender is None:
        print(f"[{role}] Error: Pokemon not set up correctly")
        return None, None
    
    print(f"[{role}] Received ATTACK_ANNOUNCE: {attacker.name} uses {move_name} on {defender.name}")
    
    # Step 2: Store the attack information in the battle manager
    battle_manager = peer.battle_manager
    battle_manager.pending_attacker = attacker
    battle_manager.pending_defender = defender
    
    # Create a Move object for damage calculation
    # The move type is based on the attacker's primary type
    move_type = attacker.type1.lower()
    damage_category = get_damage_category(move_type)
    
    battle_manager.pending_move = Move(
        name=move_name,
        base_power=1,
        category=damage_category,
        move_type=move_type,
    )
    
    # Step 3: Create DEFENSE_ANNOUNCE to confirm we received the attack
    defense_message = MessageFactory.defense_announce()
    print(f"[{role}] Sending DEFENSE_ANNOUNCE")
    
    # Transition to PROCESSING_TURN phase
    battle_manager.battle_phase = BattlePhase.PROCESSING_TURN
    print(f"[{role}] Entering PROCESSING_TURN state")
    
    # Step 4: Check if we had armed a defense boost
    battle_manager.consume_armed_defense_boost()
    defense_multiplier = battle_manager.get_defense_multiplier()
    
    # Step 5: Calculate the damage
    print(f"[{role}] Before attack: {defender.name} HP = {defender.current_hp}")
    
    battle_state = BattleState(attacker=attacker, defender=defender)
    damage = calculate_damage(
        battle_state,
        battle_manager.pending_move,
        attack_boost=1.0,  # We don't know if opponent used attack boost
        defense_boost=defense_multiplier,
    )
    
    # Calculate defender's HP after damage (minimum 0)
    defender_hp_remaining = defender.current_hp - damage
    if defender_hp_remaining < 0:
        defender_hp_remaining = 0
    
    # Store our calculation for later comparison
    battle_manager.my_calculation = {
        "damage": damage,
        "remaining_hp": defender_hp_remaining,
    }
    print(f"[{role}] Calculated damage: {damage}")
    
    # Step 6: Create CALCULATION_REPORT with our calculation
    calculation_report = battle_manager.create_calculation_report(
        attacker, defender, damage
    )
    print(f"[{role}] Sending CALCULATION_REPORT")
    
    return defense_message, calculation_report


# =============================================================================
# DEFENSE_ANNOUNCE HANDLER
# =============================================================================

def handle_defense_announce(kv: dict, peer, is_host: bool = True):
    """
    Handle a DEFENSE_ANNOUNCE message - opponent acknowledged our attack.
    
    This is Step 2 of the attack flow from the attacker's perspective.
    
    What this function does:
    1. Confirm the opponent received our attack
    2. Calculate the damage (now that we know defense was acknowledged)
    3. Create CALCULATION_REPORT with our calculation
    
    Args:
        kv: The decoded message (only contains message_type)
        peer: The peer object
        is_host: True if we're the host
    
    Returns:
        CALCULATION_REPORT message to send
    """
    role = get_role_name(is_host)
    battle_manager = peer.battle_manager
    
    # Get the move name from our stored state
    if battle_manager.pending_move:
        move_name = battle_manager.pending_move.name
    else:
        move_name = "Unknown"
    
    # Get defender name from our stored state
    if peer.opp_mon:
        defender_name = peer.opp_mon.name
    else:
        defender_name = "Unknown"
    
    print(f"[{role}] Received DEFENSE_ANNOUNCE: {defender_name} acknowledged {move_name}")
    
    # Transition to PROCESSING_TURN phase
    battle_manager.battle_phase = BattlePhase.PROCESSING_TURN
    print(f"[{role}] Entering PROCESSING_TURN state")
    
    # Make sure we have all the info we need
    if not battle_manager.pending_attacker:
        print(f"[{role}] Error: No attacker stored")
        return None
    if not battle_manager.pending_defender:
        print(f"[{role}] Error: No defender stored")
        return None
    if not battle_manager.pending_move:
        print(f"[{role}] Error: No move stored")
        return None
    
    # Calculate damage with our attack boost (if we used one)
    attacker = battle_manager.pending_attacker
    defender = battle_manager.pending_defender
    
    battle_state = BattleState(attacker=attacker, defender=defender)
    attack_multiplier = battle_manager.get_attack_multiplier()
    
    damage = calculate_damage(
        battle_state,
        battle_manager.pending_move,
        attack_boost=attack_multiplier,
        defense_boost=1.0,  # We don't know if opponent used defense boost
    )
    
    # Calculate defender's HP after damage (minimum 0)
    defender_hp_remaining = defender.current_hp - damage
    if defender_hp_remaining < 0:
        defender_hp_remaining = 0
    
    # Store our calculation for later comparison
    battle_manager.my_calculation = {
        "damage": damage,
        "remaining_hp": defender_hp_remaining,
    }
    print(f"[{role}] Calculated damage: {damage}, remaining HP: {defender_hp_remaining}")
    
    # Create CALCULATION_REPORT with our calculation
    calculation_report = battle_manager.create_calculation_report(
        attacker, defender, damage
    )
    print(f"[{role}] Sending CALCULATION_REPORT")
    
    return calculation_report


# =============================================================================
# CALCULATION_REPORT HANDLER
# =============================================================================

def handle_calculation_report(kv: dict, peer, is_host: bool = True):
    """
    Handle a CALCULATION_REPORT - compare opponent's calculation with ours.
    
    This is Step 3 of the attack flow.
    
    What this function does:
    1. Parse the opponent's damage calculation from the message
    2. Compare their calculation with ours
    3. If they match: send CALCULATION_CONFIRM and apply damage
    4. If they differ: send RESOLUTION_REQUEST
    
    Args:
        kv: The decoded message containing:
            - attacker: Name of attacking Pokemon
            - move_used: Name of move
            - remaining_health: Attacker's HP
            - damage_dealt: Calculated damage
            - defender_hp_remaining: Defender's HP after damage
            - status_message: Battle description
        peer: The peer object
        is_host: True if we're the host
    
    Returns:
        Tuple of (response_msg, game_over_msg_or_None, should_stop_battle)
    """
    role = get_role_name(is_host)
    battle_manager = peer.battle_manager
    
    # Step 1: Parse opponent's calculation from the message
    attacker_name = kv.get("attacker", "")
    move_name = kv.get("move_used", "")
    attacker_hp = kv.get("remaining_health", "0")
    damage_string = kv.get("damage_dealt", "0")
    hp_remaining_string = kv.get("defender_hp_remaining", "0")
    status_message = kv.get("status_message", "")
    
    print(f"[{role}] Received CALCULATION_REPORT:")
    print(f"[{role}]   Attacker: {attacker_name}")
    print(f"[{role}]   Move: {move_name}")
    print(f"[{role}]   Damage: {damage_string}")
    print(f"[{role}]   Defender HP remaining: {hp_remaining_string}")
    
    if status_message:
        print(f"[{role}]   Status: {status_message}")
    
    # Convert strings to integers
    reported_damage = int(damage_string)
    reported_hp_remaining = int(hp_remaining_string)
    
    # Step 2: Get our calculation for comparison
    if not battle_manager.my_calculation:
        print(f"[{role}] Warning: No local calculation to compare against")
        return None, None, False
    
    our_damage = battle_manager.my_calculation["damage"]
    our_hp_remaining = battle_manager.my_calculation["remaining_hp"]
    
    print(f"[{role}] Our calculation: damage={our_damage}, HP remaining={our_hp_remaining}")
    print(f"[{role}] Their calculation: damage={reported_damage}, HP remaining={reported_hp_remaining}")
    
    # Step 3: Compare calculations
    damage_matches = (our_damage == reported_damage)
    hp_matches = (our_hp_remaining == reported_hp_remaining)
    
    if damage_matches and hp_matches:
        # Calculations match! Send CALCULATION_CONFIRM
        print(f"[{role}] Calculations MATCH!")
        
        confirm_message = MessageFactory.calculation_confirm()
        
        # Apply the damage to the defender
        if battle_manager.pending_defender:
            battle_manager.pending_defender.current_hp = our_hp_remaining
            print(f"[{role}] Applied damage. {battle_manager.pending_defender.name} HP is now {our_hp_remaining}")
        
        # Check if the defender fainted (game over)
        if our_hp_remaining <= 0 and battle_manager.pending_defender:
            print(f"[{role}] {battle_manager.pending_defender.name} fainted!")
            game_over_message = battle_manager.create_game_over_message()
            print(f"[{role}] Sending GAME_OVER")
            return confirm_message, game_over_message, True
        
        return confirm_message, None, False
    
    else:
        # Calculations don't match! Send RESOLUTION_REQUEST
        print(f"[{role}] Calculations DON'T MATCH!")
        
        # Get attacker and move names for the resolution request
        if battle_manager.pending_attacker:
            attacker_name_for_resolution = battle_manager.pending_attacker.name
        else:
            attacker_name_for_resolution = "Unknown"
        
        if battle_manager.pending_move:
            move_name_for_resolution = battle_manager.pending_move.name
        else:
            move_name_for_resolution = "Unknown"
        
        resolution_message = MessageFactory.resolution_request(
            attacker_name=attacker_name_for_resolution,
            move_used=move_name_for_resolution,
            damage_dealt=our_damage,
            defender_hp_remaining=our_hp_remaining,
        )
        print(f"[{role}] Sending RESOLUTION_REQUEST with our values")
        
        return resolution_message, None, False


# =============================================================================
# CALCULATION_CONFIRM HANDLER
# =============================================================================

def handle_calculation_confirm(kv: dict, peer, is_host: bool = True):
    """
    Handle a CALCULATION_CONFIRM - opponent agrees with the damage calculation.
    
    This is Step 4 of the attack flow.
    
    What this function does:
    1. Apply the agreed-upon damage
    2. Check if defender fainted (game over)
    3. Switch turns if battle continues
    
    Args:
        kv: The decoded message (only contains message_type)
        peer: The peer object
        is_host: True if we're the host
    
    Returns:
        True if the game should continue, False if it's game over
    """
    role = get_role_name(is_host)
    battle_manager = peer.battle_manager
    
    # Get our stored calculation (both peers agreed on this)
    if not battle_manager.my_calculation:
        print(f"[{role}] Warning: No calculation stored")
        return True
    
    our_damage = battle_manager.my_calculation["damage"]
    our_hp_remaining = battle_manager.my_calculation["remaining_hp"]
    
    print(f"[{role}] Received CALCULATION_CONFIRM")
    print(f"[{role}] Applying confirmed damage: {our_damage}")
    
    # Apply the damage to the defender
    if battle_manager.pending_defender:
        battle_manager.pending_defender.current_hp = our_hp_remaining
        defender_name = battle_manager.pending_defender.name
        print(f"[{role}] {defender_name} HP is now {our_hp_remaining}")
    
    # Check if the defender fainted
    if our_hp_remaining <= 0 and battle_manager.pending_defender:
        print(f"[{role}] {battle_manager.pending_defender.name} fainted!")
        return False  # Game over
    
    # Switch turns
    battle_manager.switch_turn()
    
    # Tell the user what's happening
    if battle_manager.is_my_turn:
        print(f"[{role}] Turn switched! It's your turn. Type !attack to make a move.")
    else:
        print(f"[{role}] Turn switched! Waiting for opponent's move...")
    
    return True  # Game continues


# =============================================================================
# RESOLUTION_REQUEST HANDLER
# =============================================================================

def handle_resolution_request(kv: dict, peer, is_host: bool = True):
    """
    Handle a RESOLUTION_REQUEST - calculations didn't match, need to resolve.
    
    This happens when the two peers calculated different damage values.
    We accept the opponent's calculation and continue.
    
    What this function does:
    1. Parse opponent's calculation from the message
    2. Apply their damage value (accept their calculation)
    3. Check if defender fainted
    4. Switch turns if battle continues
    
    Args:
        kv: The decoded message containing:
            - attacker: Name of attacking Pokemon
            - move_used: Name of move
            - damage_dealt: Their calculated damage
            - defender_hp_remaining: Their calculated remaining HP
        peer: The peer object
        is_host: True if we're the host
    
    Returns:
        Tuple of (game_over_msg_or_None, should_stop, is_fatal_error)
    """
    role = get_role_name(is_host)
    battle_manager = peer.battle_manager
    
    # Parse their calculation
    attacker_name = kv.get("attacker", "Unknown")
    move_name = kv.get("move_used", "Unknown")
    their_damage_string = kv.get("damage_dealt", "0")
    their_hp_remaining_string = kv.get("defender_hp_remaining", "0")
    
    print(f"[{role}] Received RESOLUTION_REQUEST")
    print(f"[{role}]   Their damage: {their_damage_string}")
    print(f"[{role}]   Their HP remaining: {their_hp_remaining_string}")
    
    # Check that we have a local calculation to compare
    if not battle_manager.my_calculation:
        print(f"[{role}] ERROR: No local calculation exists!")
        print(f"[{role}] FATAL: Battle state inconsistent. Terminating.")
        return None, True, True  # Fatal error
    
    # Log our calculation for debugging
    print(f"[{role}]   Our damage: {battle_manager.my_calculation['damage']}")
    print(f"[{role}]   Our HP remaining: {battle_manager.my_calculation['remaining_hp']}")
    
    # Accept their calculation
    their_damage = int(their_damage_string)
    their_hp_remaining = int(their_hp_remaining_string)
    
    print(f"[{role}] Accepting their values")
    
    # Apply their damage
    if battle_manager.pending_defender:
        battle_manager.pending_defender.current_hp = their_hp_remaining
        defender_name = battle_manager.pending_defender.name
        print(f"[{role}] {defender_name} HP is now {their_hp_remaining}")
    
    # Check if the defender fainted
    if their_hp_remaining <= 0 and battle_manager.pending_defender:
        print(f"[{role}] {battle_manager.pending_defender.name} fainted!")
        game_over_message = battle_manager.create_game_over_message()
        print(f"[{role}] Sending GAME_OVER")
        return game_over_message, True, False
    
    # Switch turns
    battle_manager.switch_turn()
    
    # Tell the user what's happening
    if battle_manager.is_my_turn:
        print(f"[{role}] Resolution accepted. It's your turn. Type !attack to make a move.")
    else:
        print(f"[{role}] Resolution accepted. Waiting for opponent's move...")
    
    return None, False, False


# =============================================================================
# GAME_OVER HANDLER
# =============================================================================

def handle_game_over(kv: dict, peer, is_host: bool = True):
    """
    Handle a GAME_OVER message - the battle has ended!
    
    What this function does:
    1. Parse the winner and loser names
    2. Display the result
    
    Args:
        kv: The decoded message containing:
            - winner: Name of the winning Pokemon
            - loser: Name of the losing Pokemon
        peer: The peer object
        is_host: True if we're the host
    """
    role = get_role_name(is_host)
    
    winner = kv.get("winner", "Unknown")
    loser = kv.get("loser", "Unknown")
    
    print(f"[{role}] ========================================")
    print(f"[{role}] GAME OVER!")
    print(f"[{role}] {winner} defeated {loser}!")
    print(f"[{role}] ========================================")
