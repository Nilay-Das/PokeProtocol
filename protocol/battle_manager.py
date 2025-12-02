"""
Battle manager for coordinating battle flow between peers.
Handles turn tracking, damage calculation flow, and game state.
"""

from protocol.battle_state import (
    Move,
    BattleState,
    BattlePhase,
    calculate_damage,
    get_damage_category,
)


class BattleManager:
    """
    Manages battle state and coordination for a peer.
    Extracted from host/joiner to provide shared battle logic.
    """

    def __init__(self, is_host=True):
        """
        Initialize battle manager.

        Args:
            is_host: Whether this peer is the host (determines who goes first)
        """
        self.is_host = is_host
        self.battle_phase = None  # BattlePhase enum
        self.is_my_turn = is_host  # Host goes first
        self.pending_move = None  # Current move being processed
        self.my_calculation = None  # Local damage calculation for comparison
        self.pending_attacker = None  # Attacker for current turn
        self.pending_defender = None  # Defender for current turn

    def reset_turn_state(self):
        """Reset state after a turn completes."""
        self.pending_move = None
        self.my_calculation = None
        self.pending_attacker = None
        self.pending_defender = None

    def switch_turn(self):
        """Switch to the other player's turn."""
        self.is_my_turn = not self.is_my_turn
        self.battle_phase = BattlePhase.WAITING_FOR_MOVE
        self.reset_turn_state()

    def can_attack(self):
        """Check if the peer can currently attack."""
        return self.is_my_turn and self.battle_phase == BattlePhase.WAITING_FOR_MOVE

    def build_move_from_name(self, move_name: str, attacker) -> Move:
        """
        Build a Move object from a move name and attacker.

        Args:
            move_name: Name of the move
            attacker: Pokemon using the move

        Returns:
            Move object
        """
        move_type = attacker.type1.lower()
        damage_category = get_damage_category(move_type)
        return Move(
            name=move_name,
            base_power=1,
            category=damage_category,
            move_type=move_type,
        )

    def prepare_attack(self, attacker, defender, move_name: str):
        """
        Prepare an attack by setting up pending state.

        Args:
            attacker: Attacking Pokemon
            defender: Defending Pokemon
            move_name: Name of the move

        Returns:
            dict: ATTACK_ANNOUNCE message
        """
        self.pending_attacker = attacker
        self.pending_defender = defender
        self.pending_move = self.build_move_from_name(move_name, attacker)

        return {
            "message_type": "ATTACK_ANNOUNCE",
            "attacker_name": attacker.name,
            "defender_name": defender.name,
            "move_name": move_name,
        }

    def calculate_and_store(self, attacker, defender):
        """
        Calculate damage and store result for verification.

        Args:
            attacker: Attacking Pokemon
            defender: Defending Pokemon

        Returns:
            dict: Calculation result with damage and remaining_hp
        """
        state = BattleState(attacker=attacker, defender=defender)
        damage = calculate_damage(state, self.pending_move)
        remaining_hp = defender.current_hp - damage
        if remaining_hp < 0:
            remaining_hp = 0

        self.my_calculation = {"damage": damage, "remaining_hp": remaining_hp}
        return self.my_calculation

    def apply_damage(self, defender, hp_remaining: int):
        """
        Apply confirmed damage to a defender.

        Args:
            defender: Defending Pokemon
            hp_remaining: HP after damage
        """
        defender.current_hp = hp_remaining

    def check_game_over(self, defender) -> bool:
        """
        Check if a Pokemon has fainted.

        Args:
            defender: Pokemon to check

        Returns:
            True if Pokemon has fainted
        """
        return defender is not None and defender.current_hp <= 0

    def create_game_over_message(self) -> dict:
        """
        Create a GAME_OVER message based on current battle state.

        Returns:
            dict: GAME_OVER message
        """
        return {
            "message_type": "GAME_OVER",
            "winner": (
                self.pending_attacker.name if self.pending_attacker else "Unknown"
            ),
            "loser": self.pending_defender.name if self.pending_defender else "Unknown",
        }

    def get_role_prefix(self) -> str:
        """Get logging prefix based on role."""
        return "HOST" if self.is_host else "JOINER"
