"""
Handlers for all the different message types.
Each handler processes a specific type of message and does the right thing.
"""

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


def get_role_name(is_host: bool) -> str:
    """Returns 'HOST' or 'JOINER' for logging."""
    if is_host:
        return "HOST"
    else:
        return "JOINER"


def parse_stat_boosts(stat_boosts_str: str) -> tuple:
    """Parses the stat_boosts string from BATTLE_SETUP."""
    try:
        stat_boosts_dict = ast.literal_eval(stat_boosts_str)
        special_attack_uses = int(stat_boosts_dict.get("special_attack_uses", 5))
        special_defense_uses = int(stat_boosts_dict.get("special_defense_uses", 5))
        return (special_attack_uses, special_defense_uses)
    except (ValueError, SyntaxError):
        return (5, 5)


def handle_battle_setup(kv: dict, peer, is_host: bool = True):
    """Handles BATTLE_SETUP - opponent is telling us their pokemon."""
    
    role = get_role_name(is_host)
    
    # get opponents pokemon name
    pokemon_name = kv.get("pokemon_name")
    if not pokemon_name:
        print(f"[{role}] Error: BATTLE_SETUP missing pokemon_name")
        return None
    
    # look it up in database
    opponent_pokemon = peer.db.get(pokemon_name.lower())
    
    if not opponent_pokemon:
        print(f"[{role}] Error: Unknown Pokemon '{pokemon_name}'")
        return None
    
    peer.opp_mon = opponent_pokemon
    print(f"[{role}] Opponent chose {opponent_pokemon.name} (HP: {opponent_pokemon.current_hp})")
    
    # parse their stat boosts
    stat_boosts_str = kv.get("stat_boosts", "")
    if stat_boosts_str:
        sp_atk_uses, sp_def_uses = parse_stat_boosts(stat_boosts_str)
        peer.battle_manager.set_opponent_stat_boosts(sp_atk_uses, sp_def_uses)
    
    # ready to battle
    peer.battle_manager.battle_phase = BattlePhase.WAITING_FOR_MOVE
    print(f"[{role}] Battle setup complete! Ready to battle.")
    
    if is_host:
        print(f"[{role}] It's your turn! Type !attack to make a move.")
    else:
        print(f"[{role}] Waiting for Host's move...")
    
    return None


def handle_attack_announce(kv: dict, peer, is_host: bool = True):
    """Handles ATTACK_ANNOUNCE - opponent is attacking us!"""
    
    role = get_role_name(is_host)
    
    move_name = kv.get("move_name", "")
    
    # opponent attacks us
    attacker = peer.opp_mon
    defender = peer.pokemon
    
    if attacker is None or defender is None:
        print(f"[{role}] Error: Pokemon not set up correctly")
        return None, None
    
    print(f"[{role}] Received ATTACK_ANNOUNCE: {attacker.name} uses {move_name} on {defender.name}")
    
    # store attack info
    battle_manager = peer.battle_manager
    battle_manager.pending_attacker = attacker
    battle_manager.pending_defender = defender
    
    # create move object
    move_type = attacker.type1.lower()
    damage_category = get_damage_category(move_type)
    
    battle_manager.pending_move = Move(
        name=move_name,
        base_power=1,
        category=damage_category,
        move_type=move_type,
    )
    
    # send defense announce
    defense_message = MessageFactory.defense_announce()
    print(f"[{role}] Sending DEFENSE_ANNOUNCE")
    
    battle_manager.battle_phase = BattlePhase.PROCESSING_TURN
    print(f"[{role}] Entering PROCESSING_TURN state")
    
    # check for armed defense boost
    battle_manager.consume_armed_defense_boost()
    defense_multiplier = battle_manager.get_defense_multiplier()
    
    # calculate damage
    print(f"[{role}] Before attack: {defender.name} HP = {defender.current_hp}")
    
    battle_state = BattleState(attacker=attacker, defender=defender)
    damage = calculate_damage(
        battle_state,
        battle_manager.pending_move,
        attack_boost=1.0,
        defense_boost=defense_multiplier,
    )
    
    defender_hp_remaining = defender.current_hp - damage
    if defender_hp_remaining < 0:
        defender_hp_remaining = 0
    
    # store our calculation
    battle_manager.my_calculation = {
        "damage": damage,
        "remaining_hp": defender_hp_remaining,
    }
    print(f"[{role}] Calculated damage: {damage}")
    
    # create calculation report
    calculation_report = battle_manager.create_calculation_report(
        attacker, defender, damage
    )
    print(f"[{role}] Sending CALCULATION_REPORT")
    
    return defense_message, calculation_report


def handle_defense_announce(kv: dict, peer, is_host: bool = True):
    """Handles DEFENSE_ANNOUNCE - opponent acknowledged our attack."""
    
    role = get_role_name(is_host)
    battle_manager = peer.battle_manager
    
    if battle_manager.pending_move:
        move_name = battle_manager.pending_move.name
    else:
        move_name = "Unknown"
    
    if peer.opp_mon:
        defender_name = peer.opp_mon.name
    else:
        defender_name = "Unknown"
    
    print(f"[{role}] Received DEFENSE_ANNOUNCE: {defender_name} acknowledged {move_name}")
    
    battle_manager.battle_phase = BattlePhase.PROCESSING_TURN
    print(f"[{role}] Entering PROCESSING_TURN state")
    
    # make sure we have everything
    if not battle_manager.pending_attacker:
        print(f"[{role}] Error: No attacker stored")
        return None
    if not battle_manager.pending_defender:
        print(f"[{role}] Error: No defender stored")
        return None
    if not battle_manager.pending_move:
        print(f"[{role}] Error: No move stored")
        return None
    
    # calculate damage
    attacker = battle_manager.pending_attacker
    defender = battle_manager.pending_defender
    
    battle_state = BattleState(attacker=attacker, defender=defender)
    attack_multiplier = battle_manager.get_attack_multiplier()
    
    damage = calculate_damage(
        battle_state,
        battle_manager.pending_move,
        attack_boost=attack_multiplier,
        defense_boost=1.0,
    )
    
    defender_hp_remaining = defender.current_hp - damage
    if defender_hp_remaining < 0:
        defender_hp_remaining = 0
    
    # store our calculation
    battle_manager.my_calculation = {
        "damage": damage,
        "remaining_hp": defender_hp_remaining,
    }
    print(f"[{role}] Calculated damage: {damage}, remaining HP: {defender_hp_remaining}")
    
    # create calculation report
    calculation_report = battle_manager.create_calculation_report(
        attacker, defender, damage
    )
    print(f"[{role}] Sending CALCULATION_REPORT")
    
    return calculation_report


def handle_calculation_report(kv: dict, peer, is_host: bool = True):
    """Handles CALCULATION_REPORT - compare our calculation with theirs."""
    
    role = get_role_name(is_host)
    battle_manager = peer.battle_manager
    
    # parse their calculation
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
    
    reported_damage = int(damage_string)
    reported_hp_remaining = int(hp_remaining_string)
    
    # check our calculation
    if not battle_manager.my_calculation:
        print(f"[{role}] Warning: No local calculation to compare against")
        return None, None, False
    
    our_damage = battle_manager.my_calculation["damage"]
    our_hp_remaining = battle_manager.my_calculation["remaining_hp"]
    
    print(f"[{role}] Our calculation: damage={our_damage}, HP remaining={our_hp_remaining}")
    print(f"[{role}] Their calculation: damage={reported_damage}, HP remaining={reported_hp_remaining}")
    
    # compare
    damage_matches = (our_damage == reported_damage)
    hp_matches = (our_hp_remaining == reported_hp_remaining)
    
    if damage_matches and hp_matches:
        print(f"[{role}] Calculations MATCH!")
        
        confirm_message = MessageFactory.calculation_confirm()
        
        # apply damage
        if battle_manager.pending_defender:
            battle_manager.pending_defender.current_hp = our_hp_remaining
            print(f"[{role}] Applied damage. {battle_manager.pending_defender.name} HP is now {our_hp_remaining}")
        
        # check for game over
        if our_hp_remaining <= 0 and battle_manager.pending_defender:
            print(f"[{role}] {battle_manager.pending_defender.name} fainted!")
            game_over_message = battle_manager.create_game_over_message()
            print(f"[{role}] Sending GAME_OVER")
            return confirm_message, game_over_message, True
        
        return confirm_message, None, False
    
    else:
        print(f"[{role}] Calculations DON'T MATCH!")
        
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


def handle_calculation_confirm(kv: dict, peer, is_host: bool = True):
    """Handles CALCULATION_CONFIRM - opponent agrees with calculation."""
    
    role = get_role_name(is_host)
    battle_manager = peer.battle_manager
    
    if not battle_manager.my_calculation:
        print(f"[{role}] Warning: No calculation stored")
        return True
    
    our_damage = battle_manager.my_calculation["damage"]
    our_hp_remaining = battle_manager.my_calculation["remaining_hp"]
    
    print(f"[{role}] Received CALCULATION_CONFIRM")
    print(f"[{role}] Applying confirmed damage: {our_damage}")
    
    # apply damage
    if battle_manager.pending_defender:
        battle_manager.pending_defender.current_hp = our_hp_remaining
        defender_name = battle_manager.pending_defender.name
        print(f"[{role}] {defender_name} HP is now {our_hp_remaining}")
    
    # check for faint
    if our_hp_remaining <= 0 and battle_manager.pending_defender:
        print(f"[{role}] {battle_manager.pending_defender.name} fainted!")
        return False
    
    # switch turns
    battle_manager.switch_turn()
    
    if battle_manager.is_my_turn:
        print(f"[{role}] Turn switched! It's your turn. Type !attack to make a move.")
    else:
        print(f"[{role}] Turn switched! Waiting for opponent's move...")
    
    return True


def handle_resolution_request(kv: dict, peer, is_host: bool = True):
    """Handles RESOLUTION_REQUEST - calculations didn't match."""
    
    role = get_role_name(is_host)
    battle_manager = peer.battle_manager
    
    # get their values
    attacker_name = kv.get("attacker", "Unknown")
    move_name = kv.get("move_used", "Unknown")
    their_damage_string = kv.get("damage_dealt", "0")
    their_hp_remaining_string = kv.get("defender_hp_remaining", "0")
    
    print(f"[{role}] Received RESOLUTION_REQUEST")
    print(f"[{role}]   Their damage: {their_damage_string}")
    print(f"[{role}]   Their HP remaining: {their_hp_remaining_string}")
    
    if not battle_manager.my_calculation:
        print(f"[{role}] ERROR: No local calculation exists!")
        print(f"[{role}] FATAL: Battle state inconsistent. Terminating.")
        return None, True, True
    
    print(f"[{role}]   Our damage: {battle_manager.my_calculation['damage']}")
    print(f"[{role}]   Our HP remaining: {battle_manager.my_calculation['remaining_hp']}")
    
    # accept their values
    their_damage = int(their_damage_string)
    their_hp_remaining = int(their_hp_remaining_string)
    
    print(f"[{role}] Accepting their values")
    
    # apply their damage
    if battle_manager.pending_defender:
        battle_manager.pending_defender.current_hp = their_hp_remaining
        defender_name = battle_manager.pending_defender.name
        print(f"[{role}] {defender_name} HP is now {their_hp_remaining}")
    
    # check for faint
    if their_hp_remaining <= 0 and battle_manager.pending_defender:
        print(f"[{role}] {battle_manager.pending_defender.name} fainted!")
        game_over_message = battle_manager.create_game_over_message()
        print(f"[{role}] Sending GAME_OVER")
        return game_over_message, True, False
    
    # switch turns
    battle_manager.switch_turn()
    
    if battle_manager.is_my_turn:
        print(f"[{role}] Resolution accepted. It's your turn. Type !attack to make a move.")
    else:
        print(f"[{role}] Resolution accepted. Waiting for opponent's move...")
    
    return None, False, False


def handle_game_over(kv: dict, peer, is_host: bool = True):
    """Handles GAME_OVER - battle is done!"""
    
    role = get_role_name(is_host)
    
    winner = kv.get("winner", "Unknown")
    loser = kv.get("loser", "Unknown")
    
    print(f"[{role}] ========================================")
    print(f"[{role}] GAME OVER!")
    print(f"[{role}] {winner} defeated {loser}!")
    print(f"[{role}] ========================================")
