"""
=============================================================================
BATTLE STATE - Pokemon Battle Game Mechanics
=============================================================================

WHAT IS THIS FILE?
------------------
This file contains all the game logic for Pokemon battles:
- Pokemon class (stats, types, moves)
- Move class (attack information)
- Damage calculation
- Battle state tracking


POKEMON GAME MECHANICS EXPLAINED
--------------------------------

1. POKEMON STATS
   Every Pokemon has these stats:
   - HP (Hit Points): Health. When this reaches 0, the Pokemon faints.
   - Attack: Power of physical moves (like Tackle, Scratch)
   - Special Attack: Power of special moves (like Thunderbolt, Flamethrower)
   - Physical Defense: Reduces damage from physical moves
   - Special Defense: Reduces damage from special moves

2. TYPES
   Every Pokemon has one or two types (Fire, Water, Grass, Electric, etc.)
   Types create a rock-paper-scissors system:
   - Water beats Fire (super effective = 2x damage)
   - Fire beats Grass (super effective = 2x damage)
   - Grass beats Water (super effective = 2x damage)
   - Some types don't affect others (Ghost vs Normal = 0x damage)

3. MOVES
   Pokemon attack using moves. Each move has:
   - Base Power: How strong it is
   - Type: Determines type effectiveness
   - Category: Physical (uses Attack stat) or Special (uses Sp. Attack stat)

4. DAMAGE CALCULATION
   Our simplified formula:
   
   Damage = (Attacker's Stat * Type Multiplier) / Defender's Stat
   
   Where:
   - Attacker's Stat = Attack (physical) or Special Attack (special)
   - Type Multiplier = 0.5 (not effective), 1.0 (normal), or 2.0 (super effective)
   - Defender's Stat = Defense (physical) or Special Defense (special)


RANDOM NUMBER GENERATION (RNG)
------------------------------
Both players need to calculate the SAME damage. If they get different
answers, the game breaks! We solve this by using a "seeded" random
number generator:

- The host picks a random seed (like 12345)
- Both peers initialize their RNG with that seed
- Now both RNGs will produce the same "random" numbers!

This is used for things like critical hits or random damage variation.

=============================================================================
"""

from enum import Enum
import random


# =============================================================================
# GLOBAL RANDOM NUMBER GENERATOR
# =============================================================================

# This is our shared random number generator.
# Both peers use the same seed so they get the same "random" results.
_battle_rng = random.Random()


def initialize_battle_rng(seed: int):
    """
    Initialize the random number generator with a shared seed.
    
    Both the Host and Joiner must call this with the SAME seed value.
    This ensures both peers generate identical "random" numbers,
    which keeps their damage calculations in sync.
    
    Args:
        seed: The random seed from HANDSHAKE_RESPONSE.
              Any integer works, but both peers must use the same one.
    
    Example:
        # Host picks seed 12345 and sends it in HANDSHAKE_RESPONSE
        # Both peers then do:
        initialize_battle_rng(12345)
        
        # Now get_battle_rng().random() returns the same value for both!
    """
    global _battle_rng
    _battle_rng = random.Random(seed)
    print(f"[RNG] Initialized with seed: {seed}")


def get_battle_rng() -> random.Random:
    """
    Get the shared random number generator.
    
    Use this instead of Python's built-in random module when you need
    random numbers that must be the same for both peers.
    
    Returns:
        The seeded Random instance
    
    Example:
        rng = get_battle_rng()
        random_value = rng.random()  # Returns same value for both peers
    """
    return _battle_rng


# =============================================================================
# BATTLE PHASES
# =============================================================================

class BattlePhase(Enum):
    """
    The current phase of the battle.
    
    WAITING_FOR_MOVE: It's someone's turn to attack. Either:
        - It's your turn: Type !attack to choose a move
        - It's opponent's turn: Wait for their ATTACK_ANNOUNCE
    
    PROCESSING_TURN: An attack is happening. We're in the middle of:
        1. ATTACK_ANNOUNCE
        2. DEFENSE_ANNOUNCE
        3. CALCULATION_REPORT
        4. CALCULATION_CONFIRM
    """
    WAITING_FOR_MOVE = "WAITING_FOR_MOVE"
    PROCESSING_TURN = "PROCESSING_TURN"


# =============================================================================
# TYPE SYSTEM
# =============================================================================

# Moves are categorized as "physical" or "special" based on their type.
# Physical moves use Attack/Defense stats.
# Special moves use Special Attack/Special Defense stats.

# Types that deal physical damage
PHYSICAL_TYPES = {
    "normal",    # Tackle, Scratch, Hyper Beam
    "fighting",  # Karate Chop, Low Kick
    "flying",    # Wing Attack, Fly
    "poison",    # Poison Sting, Sludge
    "ground",    # Earthquake, Dig
    "rock",      # Rock Throw, Stone Edge
    "bug",       # Bug Bite, X-Scissor
    "ghost",     # Shadow Punch, Phantom Force
    "steel",     # Iron Tail, Metal Claw
}

# Types that deal special damage
SPECIAL_TYPES = {
    "fire",      # Flamethrower, Fire Blast
    "water",     # Water Gun, Hydro Pump
    "grass",     # Razor Leaf, Solar Beam
    "electric",  # Thunderbolt, Thunder
    "psychic",   # Psychic, Psybeam
    "ice",       # Ice Beam, Blizzard
    "dragon",    # Dragon Breath, Draco Meteor
    "dark",      # Dark Pulse, Crunch
    "fairy",     # Moonblast, Dazzling Gleam
}


def get_damage_category(move_type: str) -> str:
    """
    Determine if a move is physical or special based on its type.
    
    This affects which stats are used in damage calculation:
    - Physical: Uses Attack vs Physical Defense
    - Special: Uses Special Attack vs Special Defense
    
    Args:
        move_type: The type of the move (e.g., "fire", "water", "normal")
    
    Returns:
        "physical" or "special"
    
    Example:
        get_damage_category("fire")      # Returns "special"
        get_damage_category("fighting")  # Returns "physical"
    """
    # Convert to lowercase to handle "Fire" vs "fire"
    move_type_lower = move_type.lower()
    
    if move_type_lower in PHYSICAL_TYPES:
        return "physical"
    else:
        return "special"


# =============================================================================
# POKEMON CLASS
# =============================================================================

class Pokemon:
    """
    Represents a Pokemon in battle.
    
    A Pokemon has stats that determine how strong it is in battle,
    types that affect what moves are effective against it,
    and moves it can use to attack.
    
    Attributes:
        name: The Pokemon's name (e.g., "Pikachu")
        max_hp: Maximum hit points
        current_hp: Current hit points (starts equal to max_hp)
        attack: Physical attack power
        special_attack: Special attack power
        physical_defense: Defense against physical moves
        special_defense: Defense against special moves
        type1: Primary type (e.g., "Electric")
        type2: Secondary type, or None if single-type
        type_multipliers: Dict mapping attack types to damage multipliers
        moves: List of Move objects this Pokemon can use
    
    Example:
        pikachu = Pokemon(
            name="Pikachu",
            max_hp=100,
            current_hp=100,
            attack=55,
            special_attack=50,
            physical_defense=40,
            special_defense=50,
            type1="Electric",
            type2=None,
            type_multipliers={"ground": 2.0, "flying": 0.5, "electric": 0.5},
            moves=[thunderbolt, quick_attack]
        )
    """
    
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
        """
        Create a new Pokemon.
        
        Args:
            name: Pokemon's name
            max_hp: Maximum hit points
            current_hp: Starting hit points (usually same as max_hp)
            attack: Physical attack stat
            special_attack: Special attack stat
            physical_defense: Physical defense stat
            special_defense: Special defense stat
            type1: Primary type
            type2: Secondary type (can be None or empty string)
            type_multipliers: Dictionary of {attack_type: multiplier}
            moves: List of Move objects
        """
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


# =============================================================================
# MOVE CLASS
# =============================================================================

class Move:
    """
    Represents an attack move a Pokemon can use.
    
    Attributes:
        name: The move's name (e.g., "Thunderbolt")
        base_power: Base damage (before calculations)
        category: "physical" or "special"
        move_type: The type of the move (e.g., "Electric")
    
    Example:
        thunderbolt = Move(
            name="Thunderbolt",
            base_power=90,
            category="special",
            move_type="Electric"
        )
    """
    
    def __init__(self, name: str, base_power: int, category: str, move_type: str):
        """
        Create a new Move.
        
        Args:
            name: Name of the move
            base_power: Base damage value
            category: "physical" (uses Attack) or "special" (uses Sp. Attack)
            move_type: The move's type (affects effectiveness)
        """
        self.name = name
        self.base_power = base_power
        self.category = category
        self.move_type = move_type


# =============================================================================
# BATTLE STATE CLASS
# =============================================================================

class BattleState:
    """
    Holds the two Pokemon involved in the current attack.
    
    This is used during damage calculation to know who is attacking
    and who is defending.
    
    Attributes:
        attacker: The Pokemon using the move
        defender: The Pokemon being attacked
    
    Example:
        # Pikachu attacks Charmander
        state = BattleState(attacker=pikachu, defender=charmander)
        damage = calculate_damage(state, thunderbolt)
    """
    
    def __init__(self, attacker: Pokemon, defender: Pokemon):
        """
        Create a battle state for an attack.
        
        Args:
            attacker: The Pokemon performing the attack
            defender: The Pokemon receiving the attack
        """
        self.attacker = attacker
        self.defender = defender


# =============================================================================
# DAMAGE CALCULATION
# =============================================================================

def calculate_damage(
    state: BattleState,
    move: Move,
    attack_boost: float = 1.0,
    defense_boost: float = 1.0
) -> int:
    """
    Calculate how much damage an attack does.
    
    This is the core battle mechanic! The formula is:
    
        Damage = (Attack Stat * Type Multiplier) / Defense Stat
    
    Where:
    - Attack Stat = attacker's Attack (physical) or Sp. Attack (special)
    - Type Multiplier = how effective the move type is against defender's type
    - Defense Stat = defender's Defense (physical) or Sp. Defense (special)
    
    Args:
        state: BattleState containing the attacker and defender Pokemon
        move: The Move being used
        attack_boost: Multiplier for the attack stat (default 1.0)
                     Use 1.5 if the attacker used a special attack boost
        defense_boost: Multiplier for the defense stat (default 1.0)
                      Use 1.5 if the defender used a special defense boost
    
    Returns:
        The final damage as an integer (minimum 1 if move is effective)
    
    Example:
        # Normal attack
        damage = calculate_damage(state, thunderbolt)
        
        # Attack with boost (attacker used special attack boost)
        damage = calculate_damage(state, thunderbolt, attack_boost=1.5)
        
        # Defense with boost (defender used special defense boost)
        damage = calculate_damage(state, thunderbolt, defense_boost=1.5)
    """
    print(f"Calculating damage for move: {move.name}")
    
    # Step 1: Determine which stats to use based on move category
    # Physical moves use Attack and Physical Defense
    # Special moves use Special Attack and Special Defense
    
    if move.category == "physical":
        print("It is a physical move.")
        attacker_stat = state.attacker.attack
        defender_stat = state.defender.physical_defense
    else:
        print("It is a special move.")
        attacker_stat = state.attacker.special_attack
        defender_stat = state.defender.special_defense
    
    # Step 2: Apply stat boosts
    # If a player used their special attack/defense boost this turn,
    # the stat is multiplied by 1.5 (50% increase)
    
    attacker_stat = attacker_stat * attack_boost
    defender_stat = defender_stat * defense_boost
    
    # Print the stats (with boost indicator if applicable)
    if attack_boost > 1.0:
        print(f"Attacker stat: {attacker_stat} (boosted)")
    else:
        print(f"Attacker stat: {attacker_stat}")
    
    if defense_boost > 1.0:
        print(f"Defender stat: {defender_stat} (boosted)")
    else:
        print(f"Defender stat: {defender_stat}")
    
    # Make sure defense is at least 1 to avoid division by zero
    if defender_stat <= 0:
        defender_stat = 1
    
    # Step 3: Get type effectiveness multiplier
    # This is stored in the defender's type_multipliers dictionary
    # Example: Electric move vs Water Pokemon = 2.0 (super effective)
    
    move_type_lower = move.move_type.lower()
    
    # Default is 1.0 (normal effectiveness) if type not found
    type_multiplier = 1.0
    if move_type_lower in state.defender.type_multipliers:
        type_multiplier = state.defender.type_multipliers[move_type_lower]
    
    print(f"Type multiplier: {type_multiplier}")
    
    # Step 4: Calculate the damage using our formula
    # Damage = (Attack * Type Multiplier) / Defense
    
    raw_damage = (attacker_stat * type_multiplier) / defender_stat
    
    # Round to the nearest integer
    final_damage = int(round(raw_damage))
    
    # Ensure at least 1 damage if the move is effective
    # (If multiplier is 0, the move "had no effect" so 0 damage is correct)
    if final_damage <= 0 and type_multiplier > 0:
        final_damage = 1
    
    print(f"Damage: {final_damage}")
    
    return final_damage


def apply_damage(state: BattleState, damage: int):
    """
    Apply damage to the defending Pokemon.
    
    This reduces the defender's current_hp by the damage amount.
    HP cannot go below 0.
    
    Args:
        state: BattleState containing the defender
        damage: Amount of damage to apply
    
    Example:
        # Calculate and apply damage
        damage = calculate_damage(state, thunderbolt)
        apply_damage(state, damage)
        
        # Check if defender fainted
        if state.defender.current_hp <= 0:
            print(f"{state.defender.name} fainted!")
    """
    defender = state.defender
    
    print(f"Applying {damage} damage to {defender.name}")
    
    # Calculate new HP
    new_hp = defender.current_hp - damage
    
    # HP cannot go below 0
    if new_hp < 0:
        new_hp = 0
    
    # Update the Pokemon's HP
    defender.current_hp = new_hp
    
    print(f"{defender.name} HP: {defender.current_hp}/{defender.max_hp}")


# =============================================================================
# STATUS MESSAGE GENERATION
# =============================================================================

def generate_status_message(
    attacker_name: str,
    move_name: str,
    type_multiplier: float
) -> str:
    """
    Generate a battle status message based on type effectiveness.
    
    This creates messages like those in the Pokemon games:
    - "Pikachu used Thunderbolt! It was super effective!"
    - "Pikachu used Thunderbolt! It's not very effective..."
    - "Pikachu used Thunderbolt! It had no effect..."
    
    Args:
        attacker_name: Name of the attacking Pokemon
        move_name: Name of the move used
        type_multiplier: The type effectiveness multiplier
                        > 1.0 = super effective
                        < 1.0 = not very effective
                        = 0.0 = no effect
                        = 1.0 = normal
    
    Returns:
        A string describing what happened
    
    Example:
        # Electric vs Water (2.0x)
        msg = generate_status_message("Pikachu", "Thunderbolt", 2.0)
        # Returns: "Pikachu used Thunderbolt! It was super effective!"
        
        # Electric vs Ground (0.0x)
        msg = generate_status_message("Pikachu", "Thunderbolt", 0.0)
        # Returns: "Pikachu used Thunderbolt! It had no effect..."
    """
    # Base message that's always included
    base_message = f"{attacker_name} used {move_name}!"
    
    # Add effectiveness text based on the multiplier
    if type_multiplier == 0:
        return f"{base_message} It had no effect..."
    elif type_multiplier < 1:
        return f"{base_message} It's not very effective..."
    elif type_multiplier > 1:
        return f"{base_message} It was super effective!"
    else:
        # Normal effectiveness (1.0x), no extra text
        return base_message
