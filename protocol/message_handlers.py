"""
Message handlers for processing battle protocol messages.
These handlers are shared between host and joiner peers.
"""
from protocol.messages import encode_message
from protocol.battle_state import Move, BattleState, BattlePhase, calculate_damage, get_damage_category


def handle_battle_setup(kv, peer, is_host=True):
    """
    Handle BATTLE_SETUP message from the other peer.
    Sets up opponent's Pokemon and transitions to battle phase.
    
    Args:
        kv: Decoded message dictionary
        peer: The peer instance (host or joiner)
        is_host: Whether this peer is the host
    
    Returns:
        dict or None: Response message to send, if any
    """
    pname = kv.get("pokemon_name")
    if not pname:
        return None
        
    peer.opp_mon = peer.db.get(pname.lower())
    if not peer.opp_mon:
        print(f"[{'Host' if is_host else 'Joiner'}] Received BATTLE_SETUP with unknown Pokémon: {pname}")
        return None
        
    print(f"[{'Host' if is_host else 'Joiner'}] Opponent chose {peer.opp_mon.name} (HP {peer.opp_mon.current_hp})")
    
    # Transition to WAITING_FOR_MOVE state
    peer.battle_manager.battle_phase = BattlePhase.WAITING_FOR_MOVE
    print(f"[{'HOST' if is_host else 'JOINER'}] Battle setup complete! Entering {peer.battle_manager.battle_phase.value} state.")
    
    if is_host:
        print("[HOST] It's your turn! Type !attack to make a move.")
    else:
        print("[JOINER] Waiting for Host's move...")
    
    return None


def handle_attack_announce(kv, peer, is_host=True):
    """
    Handle ATTACK_ANNOUNCE message - opponent is attacking us.
    
    Args:
        kv: Decoded message dictionary
        peer: The peer instance
        is_host: Whether this peer is the host
        
    Returns:
        tuple: (defense_msg, report_msg) to send
    """
    attacker_name = kv.get("attacker_name", "")
    defender_name = kv.get("defender_name", "")
    move_name = kv.get("move_name", "")
    
    role = "HOST" if is_host else "JOINER"
    print(f"[{role}] Received ATTACK_ANNOUNCE: {attacker_name} uses {move_name} on {defender_name}")
    
    # Mapping names to the local Pokémon objects
    attacker = peer.opp_mon  # Opponent's Pokemon is attacking
    defender = peer.pokemon  # Our Pokemon is defending
    
    if attacker is None or defender is None:
        print(f"[{role}] Battle not set up correctly (missing attacker/defender).")
        return None, None
    
    # Store pending move info
    peer.battle_manager.pending_attacker = attacker
    peer.battle_manager.pending_defender = defender
    
    # Create the move with damage category based on type
    move_type = attacker.type1.lower()
    damage_category = get_damage_category(move_type)
    peer.battle_manager.pending_move = Move(
        name=move_name,
        base_power=1,
        category=damage_category,
        move_type=move_type,
    )
    
    # Send DEFENSE_ANNOUNCE to confirm receipt
    defense_msg = {
        "message_type": "DEFENSE_ANNOUNCE",
        "defender_name": defender.name,
        "acknowledged_move": move_name,
    }
    print(f"[{role}] Sending DEFENSE_ANNOUNCE: {defense_msg}")
    
    # Transition to PROCESSING_TURN
    peer.battle_manager.battle_phase = BattlePhase.PROCESSING_TURN
    print(f"[{role}] Entering {peer.battle_manager.battle_phase.value} state.")
    
    # Calculate damage locally (don't apply yet)
    state = BattleState(attacker=attacker, defender=defender)
    print(f"[{role}] Before attack: {defender.name} HP = {defender.current_hp}")
    damage = calculate_damage(state, peer.battle_manager.pending_move)
    
    # Store calculation for comparison
    peer.battle_manager.my_calculation = {
        "damage": damage,
        "remaining_hp": defender.current_hp - damage if defender.current_hp - damage > 0 else 0
    }
    print(f"[{role}] Calculated damage: {damage}")
    
    # Send CALCULATION_REPORT
    report = {
        "message_type": "CALCULATION_REPORT",
        "attacker_name": attacker.name,
        "defender_name": defender.name,
        "move_name": peer.battle_manager.pending_move.name,
        "damage_dealt": str(damage),
        "defender_hp_remaining": str(peer.battle_manager.my_calculation["remaining_hp"]),
    }
    print(f"[{role}] Sending CALCULATION_REPORT: {report}")
    
    return defense_msg, report


def handle_defense_announce(kv, peer, is_host=True):
    """
    Handle DEFENSE_ANNOUNCE message - defender acknowledged the attack.
    
    Args:
        kv: Decoded message dictionary
        peer: The peer instance
        is_host: Whether this peer is the host
        
    Returns:
        dict or None: CALCULATION_REPORT message to send
    """
    defender_name = kv.get("defender_name", "")
    acknowledged_move = kv.get("acknowledged_move", "")
    role = "HOST" if is_host else "JOINER"
    
    print(f"[{role}] Received DEFENSE_ANNOUNCE: {defender_name} acknowledged {acknowledged_move}")
    
    # Transition to PROCESSING_TURN
    peer.battle_manager.battle_phase = BattlePhase.PROCESSING_TURN
    print(f"[{role}] Entering {peer.battle_manager.battle_phase.value} state.")
    
    bm = peer.battle_manager
    if bm.pending_attacker and bm.pending_defender and bm.pending_move:
        state = BattleState(attacker=bm.pending_attacker, defender=bm.pending_defender)
        damage = calculate_damage(state, bm.pending_move)
        remaining_hp = bm.pending_defender.current_hp - damage
        if remaining_hp < 0:
            remaining_hp = 0
        
        # Store calculation for comparison
        bm.my_calculation = {
            "damage": damage,
            "remaining_hp": remaining_hp
        }
        print(f"[{role}] Calculated damage: {damage}, remaining HP: {remaining_hp}")
        
        # Send CALCULATION_REPORT
        report = {
            "message_type": "CALCULATION_REPORT",
            "attacker_name": bm.pending_attacker.name,
            "defender_name": bm.pending_defender.name,
            "move_name": bm.pending_move.name,
            "damage_dealt": str(damage),
            "defender_hp_remaining": str(remaining_hp),
        }
        print(f"[{role}] Sending CALCULATION_REPORT: {report}")
        return report
    else:
        print(f"[{role}] Error: No pending move info for calculation")
        return None


def handle_calculation_report(kv, peer, is_host=True):
    """
    Handle incoming CALCULATION_REPORT - compare with our calculation.
    
    Args:
        kv: Decoded message dictionary
        peer: The peer instance
        is_host: Whether this peer is the host
        
    Returns:
        tuple: (response_msg, game_over_msg or None, should_stop)
    """
    role = "HOST" if is_host else "JOINER"
    
    attacker_name = kv.get("attacker_name", "")
    defender_name = kv.get("defender_name", "")
    move_name = kv.get("move_name", "")
    damage_str = kv.get("damage_dealt", "0")
    hp_str = kv.get("defender_hp_remaining", "0")
    
    print(f"[{role}] Received CALCULATION_REPORT: {kv}")
    
    reported_damage = int(damage_str)
    reported_hp = int(hp_str)
    
    bm = peer.battle_manager
    
    if not bm.my_calculation:
        print(f"[{role}] Warning: No local calculation to compare against")
        return None, None, False
    
    local_damage = bm.my_calculation["damage"]
    local_remaining_hp = bm.my_calculation["remaining_hp"]
    
    print(f"[{role}] Local damage = {local_damage}, reported damage = {reported_damage}")
    print(f"[{role}] Local remaining HP = {local_remaining_hp}, reported HP = {reported_hp}")
    
    if local_damage == reported_damage and local_remaining_hp == reported_hp:
        # Calculations match - send CALCULATION_CONFIRM
        confirm_msg = {
            "message_type": "CALCULATION_CONFIRM",
            "damage_confirmed": str(local_damage),
            "remaining_health": str(local_remaining_hp),
        }
        print(f"[{role}] Calculations match! Sending CALCULATION_CONFIRM: {confirm_msg}")
        
        # Apply damage to the defender
        if bm.pending_defender:
            bm.pending_defender.current_hp = local_remaining_hp
            print(f"[{role}] Applied damage. {bm.pending_defender.name} HP is now {bm.pending_defender.current_hp}")
        
        # Check for game over
        if local_remaining_hp <= 0 and bm.pending_defender:
            print(f"[{role}] {bm.pending_defender.name} fainted!")
            game_over_msg = {
                "message_type": "GAME_OVER",
                "winner": bm.pending_attacker.name if bm.pending_attacker else "Unknown",
                "loser": bm.pending_defender.name,
            }
            print(f"[{role}] Sending GAME_OVER: {game_over_msg}")
            return confirm_msg, game_over_msg, True
        
        return confirm_msg, None, False
    else:
        # Calculations don't match - send RESOLUTION_REQUEST
        resolution_msg = {
            "message_type": "RESOLUTION_REQUEST",
            "calculated_damage": str(local_damage),
            "calculated_remaining_hp": str(local_remaining_hp),
            "attacker_stat": str(
                bm.pending_attacker.attack 
                if bm.pending_move and bm.pending_move.category == "physical" 
                else bm.pending_attacker.special_attack
            ) if bm.pending_attacker else "0",
            "defender_stat": str(
                bm.pending_defender.physical_defense 
                if bm.pending_move and bm.pending_move.category == "physical" 
                else bm.pending_defender.special_defense
            ) if bm.pending_defender else "0",
            "type_multiplier": str(
                bm.pending_defender.type_multipliers.get(bm.pending_move.move_type, 1.0)
            ) if bm.pending_defender and bm.pending_move else "1.0",
        }
        print(f"[{role}] Calculations DON'T match! Sending RESOLUTION_REQUEST: {resolution_msg}")
        return resolution_msg, None, False


def handle_calculation_confirm(kv, peer, is_host=True):
    """
    Handle CALCULATION_CONFIRM - apply the confirmed damage and switch turns.
    
    Args:
        kv: Decoded message dictionary
        peer: The peer instance
        is_host: Whether this peer is the host
        
    Returns:
        bool: True if game should continue, False if game over
    """
    role = "HOST" if is_host else "JOINER"
    
    damage_confirmed = kv.get("damage_confirmed", "0")
    remaining_health = kv.get("remaining_health", "0")
    
    print(f"[{role}] Received CALCULATION_CONFIRM: damage={damage_confirmed}, remaining_hp={remaining_health}")
    
    bm = peer.battle_manager
    
    # Apply damage
    if bm.pending_defender:
        bm.pending_defender.current_hp = int(remaining_health)
        print(f"[{role}] Applied confirmed damage. {bm.pending_defender.name} HP is now {bm.pending_defender.current_hp}")
    
    # Check for game over
    if int(remaining_health) <= 0 and bm.pending_defender:
        print(f"[{role}] {bm.pending_defender.name} fainted!")
        return False  # Game over
    
    # Switch turns and return to WAITING_FOR_MOVE
    bm.is_my_turn = not bm.is_my_turn
    bm.battle_phase = BattlePhase.WAITING_FOR_MOVE
    bm.pending_move = None
    bm.my_calculation = None
    
    if bm.is_my_turn:
        print(f"[{role}] Turn switched! It's your turn. Type !attack to make a move.")
    else:
        print(f"[{role}] Turn switched! Waiting for opponent's move...")
    
    return True  # Game continues


def handle_resolution_request(kv, peer, is_host=True):
    """
    Handle RESOLUTION_REQUEST - other peer's calculation didn't match.
    
    Args:
        kv: Decoded message dictionary
        peer: The peer instance
        is_host: Whether this peer is the host
        
    Returns:
        tuple: (game_over_msg or None, should_stop, is_fatal_error)
    """
    role = "HOST" if is_host else "JOINER"
    
    their_damage = kv.get("calculated_damage", "0")
    their_remaining_hp = kv.get("calculated_remaining_hp", "0")
    their_atk_stat = kv.get("attacker_stat", "0")
    their_def_stat = kv.get("defender_stat", "0")
    their_multiplier = kv.get("type_multiplier", "1.0")
    
    print(f"[{role}] Received RESOLUTION_REQUEST: {kv}")
    print(f"[{role}] Their values - damage: {their_damage}, remaining_hp: {their_remaining_hp}")
    print(f"[{role}] Their stats - atk: {their_atk_stat}, def: {their_def_stat}, multiplier: {their_multiplier}")
    
    bm = peer.battle_manager
    
    if not bm.my_calculation:
        print(f"[{role}] Error: Received RESOLUTION_REQUEST but no local calculation exists")
        print(f"[{role}] FATAL: Battle state inconsistent. Terminating.")
        return None, True, True  # Fatal error
    
    print(f"[{role}] Our values - damage: {bm.my_calculation['damage']}, remaining_hp: {bm.my_calculation['remaining_hp']}")
    
    # Accept their calculation and update state
    their_damage_int = int(their_damage)
    their_hp_int = int(their_remaining_hp)
    
    print(f"[{role}] Accepting resolution values. Applying damage: {their_damage_int}")
    
    if bm.pending_defender:
        bm.pending_defender.current_hp = their_hp_int
        print(f"[{role}] {bm.pending_defender.name} HP is now {their_hp_int}")
    
    # Check for game over
    if their_hp_int <= 0 and bm.pending_defender:
        print(f"[{role}] {bm.pending_defender.name} fainted!")
        game_over_msg = {
            "message_type": "GAME_OVER",
            "winner": bm.pending_attacker.name if bm.pending_attacker else "Unknown",
            "loser": bm.pending_defender.name,
        }
        print(f"[{role}] Sending GAME_OVER: {game_over_msg}")
        return game_over_msg, True, False
    
    # Switch turns
    bm.is_my_turn = not bm.is_my_turn
    bm.battle_phase = BattlePhase.WAITING_FOR_MOVE
    bm.pending_move = None
    bm.my_calculation = None
    
    if bm.is_my_turn:
        print(f"[{role}] Resolution accepted. It's your turn. Type !attack to make a move.")
    else:
        print(f"[{role}] Resolution accepted. Waiting for opponent's move...")
    
    return None, False, False


def handle_game_over(kv, peer, is_host=True):
    """
    Handle GAME_OVER message.
    
    Args:
        kv: Decoded message dictionary
        peer: The peer instance
        is_host: Whether this peer is the host
    """
    role = "HOST" if is_host else "JOINER"
    
    winner = kv.get("winner", "Unknown")
    loser = kv.get("loser", "Unknown")
    print(f"[{role}] GAME_OVER: {winner} defeated {loser}")

