"""
Pokemon battle game logic.
Has the Pokemon class, Move class, and damage calculation stuff.
"""

from enum import Enum
import random


# global RNG that both peers share
_battle_rng = random.Random()


def initialize_battle_rng(seed: int):
    """Sets up the random number generator with a seed so both peers get same results."""
    global _battle_rng
    _battle_rng = random.Random(seed)
    print(f"[RNG] Initialized with seed: {seed}")


def get_battle_rng() -> random.Random:
    """Gets the shared RNG."""
    return _battle_rng


class BattlePhase(Enum):
    """What phase the battle is in."""
    WAITING_FOR_MOVE = "WAITING_FOR_MOVE"
    PROCESSING_TURN = "PROCESSING_TURN"


# types that use physical attack/defense
PHYSICAL_TYPES = {
    "normal", "fighting", "flying", "poison", "ground",
    "rock", "bug", "ghost", "steel",
}

# types that use special attack/defense
SPECIAL_TYPES = {
    "fire", "water", "grass", "electric", "psychic",
    "ice", "dragon", "dark", "fairy",
}


def get_damage_category(move_type: str) -> str:
    """Returns 'physical' or 'special' based on the move type."""
    move_type_lower = move_type.lower()
    
    if move_type_lower in PHYSICAL_TYPES:
        return "physical"
    else:
        return "special"


class Pokemon:
    """A pokemon with stats, types, and moves."""
    
    def __init__(
        self,
        name: str,
        max_hp: int,
        current_hp: int,
        attack: int,
        special_attack: int,
        physical_defense: int,
        special_defense: int,
        type1: str,
        type2: str,
        type_multipliers: dict,
        moves: list,
    ):
        """Creates a pokemon with all its stats."""
        self.name = name
        self.max_hp = max_hp
        self.current_hp = current_hp
        self.attack = attack
        self.special_attack = special_attack
        self.physical_defense = physical_defense
        self.special_defense = special_defense
        self.type1 = type1
        self.type2 = type2
        self.type_multipliers = type_multipliers
        self.moves = moves


class Move:
    """An attack move a pokemon can use."""
    
    def __init__(self, name: str, base_power: int, category: str, move_type: str):
        """Creates a move."""
        self.name = name
        self.base_power = base_power
        self.category = category
        self.move_type = move_type


class BattleState:
    """Holds the attacker and defender for a turn."""
    
    def __init__(self, attacker: Pokemon, defender: Pokemon):
        """Sets up who is attacking who."""
        self.attacker = attacker
        self.defender = defender


def calculate_damage(
    state: BattleState,
    move: Move,
    attack_boost: float = 1.0,
    defense_boost: float = 1.0
) -> int:
    """Calculates how much damage an attack does."""
    
    print(f"Calculating damage for move: {move.name}")
    
    # figure out which stats to use
    if move.category == "physical":
        print("It is a physical move.")
        attacker_stat = state.attacker.attack
        defender_stat = state.defender.physical_defense
    else:
        print("It is a special move.")
        attacker_stat = state.attacker.special_attack
        defender_stat = state.defender.special_defense
    
    # apply boosts
    attacker_stat = attacker_stat * attack_boost
    defender_stat = defender_stat * defense_boost
    
    if attack_boost > 1.0:
        print(f"Attacker stat: {attacker_stat} (boosted)")
    else:
        print(f"Attacker stat: {attacker_stat}")
    
    if defense_boost > 1.0:
        print(f"Defender stat: {defender_stat} (boosted)")
    else:
        print(f"Defender stat: {defender_stat}")
    
    # dont divide by zero
    if defender_stat <= 0:
        defender_stat = 1
    
    # get type effectiveness
    move_type_lower = move.move_type.lower()
    type_multiplier = 1.0
    if move_type_lower in state.defender.type_multipliers:
        type_multiplier = state.defender.type_multipliers[move_type_lower]
    
    print(f"Type multiplier: {type_multiplier}")
    
    # calculate damage
    raw_damage = (attacker_stat * type_multiplier) / defender_stat
    final_damage = int(round(raw_damage))
    
    # at least 1 damage if move is effective
    if final_damage <= 0 and type_multiplier > 0:
        final_damage = 1
    
    print(f"Damage: {final_damage}")
    
    return final_damage


def apply_damage(state: BattleState, damage: int):
    """Applies damage to the defender."""
    
    defender = state.defender
    
    print(f"Applying {damage} damage to {defender.name}")
    
    new_hp = defender.current_hp - damage
    
    # hp cant go below 0
    if new_hp < 0:
        new_hp = 0
    
    defender.current_hp = new_hp
    
    print(f"{defender.name} HP: {defender.current_hp}/{defender.max_hp}")


def generate_status_message(
    attacker_name: str,
    move_name: str,
    type_multiplier: float
) -> str:
    """Makes a message like 'Pikachu used Thunderbolt! Its super effective!'"""
    
    base_message = f"{attacker_name} used {move_name}!"
    
    if type_multiplier == 0:
        return f"{base_message} It had no effect..."
    elif type_multiplier < 1:
        return f"{base_message} It's not very effective..."
    elif type_multiplier > 1:
        return f"{base_message} It was super effective!"
    else:
        return base_message
