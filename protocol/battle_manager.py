"""
=============================================================================
BATTLE MANAGER - Coordinating the Battle Flow
=============================================================================

WHAT IS THIS FILE?
------------------
This file manages the state and flow of a Pokemon battle. It's like a
referee that keeps track of:
- Whose turn is it?
- What move is being used?
- Did both players calculate the same damage?
- Did anyone's Pokemon faint?


BATTLE FLOW OVERVIEW
--------------------
A Pokemon battle follows this turn-based structure:

1. SETUP PHASE
   - Both peers exchange BATTLE_SETUP messages
   - Each peer knows their Pokemon and their opponent's Pokemon
   - Host goes first (is_my_turn = True for host)

2. ATTACK PHASE (repeats until someone wins)

   a) Attacker's Actions:
      - Choose a move (e.g., "Thunderbolt")
      - Optionally use a special attack boost (1.5x attack power)
      - Send ATTACK_ANNOUNCE message

   b) Defender's Actions:
      - Receive ATTACK_ANNOUNCE
      - Optionally use a special defense boost (1.5x defense power)
      - Send DEFENSE_ANNOUNCE message

   c) Damage Calculation:
      - Both peers independently calculate the damage
      - Both send CALCULATION_REPORT with their results
      - If results match: send CALCULATION_CONFIRM
      - If results differ: send RESOLUTION_REQUEST

   d) Turn Ends:
      - Apply damage to defender's Pokemon
      - Check if defender fainted (HP <= 0)
      - If fainted: send GAME_OVER
      - If not: switch turns and repeat

3. GAME OVER
   - One Pokemon's HP reaches 0
   - Winner and loser announced


STAT BOOSTS EXPLAINED
---------------------
Each player starts with:
- 5 Special Attack boosts (makes your attacks 1.5x stronger)
- 5 Special Defense boosts (reduces incoming damage to 1/1.5x)

How to use them:
- Attack boost: Activate BEFORE sending ATTACK_ANNOUNCE
- Defense boost: Activate BEFORE opponent attacks (use !defend command)

Once used, a boost is consumed and cannot be used again.

=============================================================================
"""

from protocol.battle_state import (
    Move,
    BattleState,
    BattlePhase,
    calculate_damage,
    get_damage_category,
    generate_status_message,
)
from protocol.message_factory import MessageFactory
from protocol.constants import DEFAULT_SPECIAL_ATTACK_USES, DEFAULT_SPECIAL_DEFENSE_USES


class BattleManager:
    """
    Manages the state and flow of a Pokemon battle.

    This class is used by both the Host and Joiner peers to:
    - Track whose turn it is
    - Track what move is being used
    - Handle stat boosts
    - Create protocol messages
    - Verify damage calculations

    Example usage:
        # Create a battle manager for the host
        manager = BattleManager(is_host=True)

        # Check if it's our turn to attack
        if manager.can_attack():
            attack_msg = manager.prepare_attack(my_pokemon, opponent_pokemon, "Thunderbolt")
            # Send attack_msg to opponent

        # After damage is confirmed, switch turns
        manager.switch_turn()
    """

    def __init__(self, is_host: bool = True):
        """
        Initialize the battle manager.

        Args:
            is_host: True if this is the host peer, False if joiner.
                    The host always goes first!
        """
        # Remember if we're the host or joiner
        self.is_host = is_host

        # Current phase of the battle (WAITING_FOR_MOVE or PROCESSING_TURN)
        self.battle_phase = None

        # Is it currently our turn to attack?
        # Host goes first, so is_my_turn starts as True for host, False for joiner
        self.is_my_turn = is_host

        # Information about the current attack being processed
        # These are set when an attack starts and cleared when the turn ends
        self.pending_move = None  # The Move object being used
        self.pending_attacker = None  # Pokemon doing the attack
        self.pending_defender = None  # Pokemon being attacked

        # Our damage calculation, stored so we can compare with opponent's
        self.my_calculation = None

        # =====================================================================
        # STAT BOOST TRACKING
        # Each player starts with 5 of each type of boost
        # =====================================================================

        # Our available boosts
        self.special_attack_uses = DEFAULT_SPECIAL_ATTACK_USES  # 5 by default
        self.special_defense_uses = DEFAULT_SPECIAL_DEFENSE_USES  # 5 by default

        # Opponent's available boosts (received in their BATTLE_SETUP)
        self.opp_special_attack_uses = DEFAULT_SPECIAL_ATTACK_USES
        self.opp_special_defense_uses = DEFAULT_SPECIAL_DEFENSE_USES

        # Flags for whether we're using a boost THIS TURN
        self.use_special_attack_boost = False
        self.use_special_defense_boost = False

        # Defense boost can be "armed" before opponent attacks
        # When they attack, the armed boost is automatically consumed
        self.defense_boost_armed = False

    # =========================================================================
    # TURN MANAGEMENT
    # =========================================================================

    def reset_turn_state(self):
        """
        Reset all turn-specific state after a turn completes.

        Called automatically by switch_turn(), but can also be called
        manually if needed.
        """
        self.pending_move = None
        self.my_calculation = None
        self.pending_attacker = None
        self.pending_defender = None
        self.use_special_attack_boost = False
        self.use_special_defense_boost = False

    def switch_turn(self):
        """
        Switch to the other player's turn.

        This is called after a turn completes successfully.
        It resets the turn state and toggles is_my_turn.
        """
        # Toggle whose turn it is
        self.is_my_turn = not self.is_my_turn

        # Go back to waiting for the next move
        self.battle_phase = BattlePhase.WAITING_FOR_MOVE

        # Clear all the turn-specific data
        self.reset_turn_state()

    def can_attack(self) -> bool:
        """
        Check if we can currently make an attack.

        We can attack only when:
        1. It's our turn (is_my_turn == True)
        2. We're waiting for a move (not already processing one)

        Returns:
            True if we can attack, False otherwise
        """
        # Must be our turn
        if not self.is_my_turn:
            return False

        # Must be in the WAITING_FOR_MOVE phase
        if self.battle_phase != BattlePhase.WAITING_FOR_MOVE:
            return False

        return True

    # =========================================================================
    # STAT BOOST MANAGEMENT
    # =========================================================================

    def set_stat_boosts(self, special_attack_uses: int, special_defense_uses: int):
        """
        Set our stat boost allocation.

        This is typically called during battle setup.

        Args:
            special_attack_uses: Number of attack boosts we have
            special_defense_uses: Number of defense boosts we have
        """
        self.special_attack_uses = special_attack_uses
        self.special_defense_uses = special_defense_uses

        role = self.get_role_prefix()
        print(
            f"[{role}] Stat boosts set: SpAtk={special_attack_uses}, SpDef={special_defense_uses}"
        )

    def set_opponent_stat_boosts(
        self, special_attack_uses: int, special_defense_uses: int
    ):
        """
        Set the opponent's stat boost allocation.

        This is learned from their BATTLE_SETUP message.

        Args:
            special_attack_uses: Number of attack boosts they have
            special_defense_uses: Number of defense boosts they have
        """
        self.opp_special_attack_uses = special_attack_uses
        self.opp_special_defense_uses = special_defense_uses

        role = self.get_role_prefix()
        print(
            f"[{role}] Opponent stat boosts: SpAtk={special_attack_uses}, SpDef={special_defense_uses}"
        )

    def use_special_attack(self) -> bool:
        """
        Use a special attack boost for this turn.

        When activated, your attack power is multiplied by 1.5x.
        You can only use this if you have uses remaining.

        Returns:
            True if the boost was activated, False if no uses left
        """
        # Check if we have any uses left
        if self.special_attack_uses <= 0:
            role = self.get_role_prefix()
            print(f"[{role}] No Special Attack boosts remaining!")
            return False

        # Use one boost
        self.special_attack_uses = self.special_attack_uses - 1
        self.use_special_attack_boost = True

        role = self.get_role_prefix()
        print(
            f"[{role}] Using Special Attack boost! ({self.special_attack_uses} remaining)"
        )
        return True

    def use_special_defense(self) -> bool:
        """
        Use a special defense boost for this turn.

        When activated, incoming damage is reduced (divided by 1.5).
        You can only use this if you have uses remaining.

        Returns:
            True if the boost was activated, False if no uses left
        """
        # Check if we have any uses left
        if self.special_defense_uses <= 0:
            role = self.get_role_prefix()
            print(f"[{role}] No Special Defense boosts remaining!")
            return False

        # Use one boost
        self.special_defense_uses = self.special_defense_uses - 1
        self.use_special_defense_boost = True

        role = self.get_role_prefix()
        print(
            f"[{role}] Using Special Defense boost! ({self.special_defense_uses} remaining)"
        )
        return True

    def arm_defense_boost(self) -> bool:
        """
        Arm a defense boost for the next incoming attack.

        Use this when you're waiting for the opponent to attack.
        When they attack, the boost will automatically activate.

        The boost isn't consumed until the attack actually happens.

        Returns:
            True if the boost was armed, False if no uses left
        """
        # Check if we have any uses left
        if self.special_defense_uses <= 0:
            role = self.get_role_prefix()
            print(f"[{role}] No Special Defense boosts remaining!")
            return False

        # Arm the boost (don't consume yet)
        self.defense_boost_armed = True

        role = self.get_role_prefix()
        print(
            f"[{role}] Special Defense boost armed for next attack! ({self.special_defense_uses} uses remaining)"
        )
        return True

    def consume_armed_defense_boost(self) -> bool:
        """
        Consume the armed defense boost when an attack comes in.

        This is called automatically when we receive an ATTACK_ANNOUNCE.
        If we had armed a defense boost, it gets activated now.

        Returns:
            True if a boost was consumed, False if none was armed
        """
        # Check if we have an armed boost AND uses remaining
        if not self.defense_boost_armed:
            return False

        if self.special_defense_uses <= 0:
            self.defense_boost_armed = False
            return False

        # Consume the boost
        self.special_defense_uses = self.special_defense_uses - 1
        self.use_special_defense_boost = True
        self.defense_boost_armed = False

        role = self.get_role_prefix()
        print(
            f"[{role}] Special Defense boost activated! ({self.special_defense_uses} remaining)"
        )
        return True

    def get_attack_multiplier(self) -> float:
        """
        Get the attack multiplier for damage calculation.

        Returns:
            1.5 if using a special attack boost, 1.0 otherwise
        """
        if self.use_special_attack_boost:
            return 1.5
        else:
            return 1.0

    def get_defense_multiplier(self) -> float:
        """
        Get the defense multiplier for damage calculation.

        Returns:
            1.5 if using a special defense boost, 1.0 otherwise
        """
        if self.use_special_defense_boost:
            return 1.5
        else:
            return 1.0

    # =========================================================================
    # ATTACK PREPARATION
    # =========================================================================

    def build_move_from_name(self, move_name: str, attacker) -> Move:
        """
        Create a Move object from a move name.

        Since our database might not have full move data, we construct
        a Move using the attacker's type to determine the damage category.

        Args:
            move_name: Name of the move (e.g., "Thunderbolt")
            attacker: The Pokemon using the move

        Returns:
            A Move object ready for damage calculation
        """
        # Use the attacker's primary type for the move
        move_type = attacker.type1.lower()

        # Determine if this is a physical or special move
        damage_category = get_damage_category(move_type)

        # Create and return the Move object
        move = Move(
            name=move_name,
            base_power=1,  # Base power isn't used in our formula
            category=damage_category,
            move_type=move_type,
        )
        return move

    def prepare_attack(self, attacker, defender, move_name: str) -> dict:
        """
        Prepare an attack and create the ATTACK_ANNOUNCE message.

        This sets up all the state needed to process the attack:
        - Records who is attacking and defending
        - Creates the Move object
        - Builds the message to send

        Args:
            attacker: The Pokemon making the attack (usually ours)
            defender: The Pokemon being attacked (opponent's)
            move_name: Name of the move to use

        Returns:
            ATTACK_ANNOUNCE message ready to send
        """
        # Store the attack information
        self.pending_attacker = attacker
        self.pending_defender = defender
        self.pending_move = self.build_move_from_name(move_name, attacker)

        # Create the message (just message_type and move_name per RFC)
        attack_message = {
            "message_type": "ATTACK_ANNOUNCE",
            "move_name": move_name,
        }
        return attack_message

    # =========================================================================
    # DAMAGE CALCULATION
    # =========================================================================

    def calculate_and_store(self, attacker, defender) -> dict:
        """
        Calculate damage and store the result for later comparison.

        Both peers do this calculation independently, then compare
        results to make sure they match.

        Args:
            attacker: Attacking Pokemon
            defender: Defending Pokemon

        Returns:
            Dictionary with 'damage' and 'remaining_hp' values
        """
        # Create battle state for the calculation
        state = BattleState(attacker=attacker, defender=defender)

        # Calculate the damage
        damage = calculate_damage(state, self.pending_move)

        # Calculate remaining HP (minimum 0)
        remaining_hp = defender.current_hp - damage
        if remaining_hp < 0:
            remaining_hp = 0

        # Store our calculation
        self.my_calculation = {"damage": damage, "remaining_hp": remaining_hp}

        return self.my_calculation

    def apply_damage(self, defender, hp_remaining: int):
        """
        Apply confirmed damage to a Pokemon.

        Called after both peers agree on the damage amount.

        Args:
            defender: The Pokemon to apply damage to
            hp_remaining: The HP value to set (already calculated)
        """
        defender.current_hp = hp_remaining

    def check_game_over(self, defender) -> bool:
        """
        Check if a Pokemon has fainted (battle is over).

        A Pokemon faints when its HP reaches 0 or below.

        Args:
            defender: The Pokemon to check

        Returns:
            True if the Pokemon has fainted, False otherwise
        """
        if defender is None:
            return False

        return defender.current_hp <= 0

    # =========================================================================
    # MESSAGE CREATION
    # =========================================================================

    def create_game_over_message(self) -> dict:
        """
        Create a GAME_OVER message announcing the battle result.

        Uses the pending_attacker as the winner and pending_defender
        as the loser (since we only call this when defender faints).

        Returns:
            GAME_OVER message ready to send
        """
        # Get winner name (the attacker)
        if self.pending_attacker is not None:
            winner_name = self.pending_attacker.name
        else:
            winner_name = "Unknown"

        # Get loser name (the defender who fainted)
        if self.pending_defender is not None:
            loser_name = self.pending_defender.name
        else:
            loser_name = "Unknown"

        # Use the factory to create the message
        return MessageFactory.game_over(
            winner_name=winner_name,
            loser_name=loser_name,
        )

    def create_calculation_report(self, attacker, defender, damage: int) -> dict:
        """
        Create a CALCULATION_REPORT message with our damage calculation.

        This message is sent after both ATTACK_ANNOUNCE and DEFENSE_ANNOUNCE.
        Both peers send their calculation, then compare to verify they match.

        Args:
            attacker: The attacking Pokemon
            defender: The defending Pokemon
            damage: The calculated damage amount

        Returns:
            CALCULATION_REPORT message ready to send
        """
        # Calculate defender's HP after damage (minimum 0)
        defender_hp_remaining = defender.current_hp - damage
        if defender_hp_remaining < 0:
            defender_hp_remaining = 0

        # Get type effectiveness for the status message
        move_type = self.pending_move.move_type.lower()
        type_multiplier = defender.type_multipliers.get(move_type, 1.0)

        # Generate a message like "Pikachu used Thunderbolt! It was super effective!"
        status_message = generate_status_message(
            attacker.name, self.pending_move.name, type_multiplier
        )

        # Use the factory to create the message
        return MessageFactory.calculation_report(
            attacker_name=attacker.name,
            move_used=self.pending_move.name,
            attacker_remaining_health=attacker.current_hp,
            damage_dealt=damage,
            defender_hp_remaining=defender_hp_remaining,
            status_message=status_message,
        )

    # =========================================================================
    # UTILITY
    # =========================================================================

    def get_role_prefix(self) -> str:
        """
        Get a string prefix for log messages.

        Returns:
            "HOST" if we're the host, "JOINER" if we're the joiner
        """
        if self.is_host:
            return "HOST"
        else:
            return "JOINER"
