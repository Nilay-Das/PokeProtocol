"""
Manages the battle flow - turns, damage calculations, etc.
Used by both Host and Joiner to keep track of what's happening.
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
    """Keeps track of battle state and handles turn logic."""

    def __init__(self, is_host: bool = True):
        """Sets up the battle manager. Host goes first."""

        self.is_host = is_host
        self.battle_phase = None
        self.is_my_turn = is_host  # host goes first

        # current attack info
        self.pending_move = None
        self.pending_attacker = None
        self.pending_defender = None
        self.my_calculation = None

        # stat boosts
        self.special_attack_uses = DEFAULT_SPECIAL_ATTACK_USES
        self.special_defense_uses = DEFAULT_SPECIAL_DEFENSE_USES
        self.opp_special_attack_uses = DEFAULT_SPECIAL_ATTACK_USES
        self.opp_special_defense_uses = DEFAULT_SPECIAL_DEFENSE_USES

        # boost flags for current turn
        self.use_special_attack_boost = False
        self.use_special_defense_boost = False
        self.defense_boost_armed = False

    def reset_turn_state(self):
        """Resets everything for a new turn."""
        self.pending_move = None
        self.my_calculation = None
        self.pending_attacker = None
        self.pending_defender = None
        self.use_special_attack_boost = False
        self.use_special_defense_boost = False

    def switch_turn(self):
        """Switches to the other players turn."""
        self.is_my_turn = not self.is_my_turn
        self.battle_phase = BattlePhase.WAITING_FOR_MOVE
        self.reset_turn_state()

    def can_attack(self) -> bool:
        """Checks if we can attack right now."""
        if not self.is_my_turn:
            return False
        if self.battle_phase != BattlePhase.WAITING_FOR_MOVE:
            return False
        return True

    def set_stat_boosts(self, special_attack_uses: int, special_defense_uses: int):
        """Sets our stat boost counts."""
        self.special_attack_uses = special_attack_uses
        self.special_defense_uses = special_defense_uses
        role = self.get_role_prefix()
        print(
            f"[{role}] Stat boosts set: SpAtk={special_attack_uses}, SpDef={special_defense_uses}"
        )

    def set_opponent_stat_boosts(
        self, special_attack_uses: int, special_defense_uses: int
    ):
        """Sets the opponents stat boost counts."""
        self.opp_special_attack_uses = special_attack_uses
        self.opp_special_defense_uses = special_defense_uses
        role = self.get_role_prefix()
        print(
            f"[{role}] Opponent stat boosts: SpAtk={special_attack_uses}, SpDef={special_defense_uses}"
        )

    def use_special_attack(self) -> bool:
        """Uses a special attack boost if we have one."""
        if self.special_attack_uses <= 0:
            role = self.get_role_prefix()
            print(f"[{role}] No Special Attack boosts remaining!")
            return False

        self.special_attack_uses = self.special_attack_uses - 1
        self.use_special_attack_boost = True
        role = self.get_role_prefix()
        print(
            f"[{role}] Using Special Attack boost! ({self.special_attack_uses} remaining)"
        )
        return True

    def use_special_defense(self) -> bool:
        """Uses a special defense boost if we have one."""
        if self.special_defense_uses <= 0:
            role = self.get_role_prefix()
            print(f"[{role}] No Special Defense boosts remaining!")
            return False

        self.special_defense_uses = self.special_defense_uses - 1
        self.use_special_defense_boost = True
        role = self.get_role_prefix()
        print(
            f"[{role}] Using Special Defense boost! ({self.special_defense_uses} remaining)"
        )
        return True

    def arm_defense_boost(self) -> bool:
        """Arms a defense boost for the next incoming attack."""
        if self.special_defense_uses <= 0:
            role = self.get_role_prefix()
            print(f"[{role}] No Special Defense boosts remaining!")
            return False

        self.defense_boost_armed = True
        role = self.get_role_prefix()
        print(
            f"[{role}] Special Defense boost armed for next attack! ({self.special_defense_uses} uses remaining)"
        )
        return True

    def consume_armed_defense_boost(self) -> bool:
        """Uses the armed defense boost when attacked."""
        if not self.defense_boost_armed:
            return False
        if self.special_defense_uses <= 0:
            self.defense_boost_armed = False
            return False

        self.special_defense_uses = self.special_defense_uses - 1
        self.use_special_defense_boost = True
        self.defense_boost_armed = False
        role = self.get_role_prefix()
        print(
            f"[{role}] Special Defense boost activated! ({self.special_defense_uses} remaining)"
        )
        return True

    def get_attack_multiplier(self) -> float:
        """Returns attack multiplier (1.5 if boosted, 1.0 otherwise)."""
        if self.use_special_attack_boost:
            return 1.5
        else:
            return 1.0

    def get_defense_multiplier(self) -> float:
        """Returns defense multiplier (1.5 if boosted, 1.0 otherwise)."""
        if self.use_special_defense_boost:
            return 1.5
        else:
            return 1.0

    def build_move_from_name(self, move_name: str, attacker) -> Move:
        """Creates a Move object from a move name."""
        move_type = attacker.type1.lower()
        damage_category = get_damage_category(move_type)
        move = Move(
            name=move_name,
            base_power=1,
            category=damage_category,
            move_type=move_type,
        )
        return move

    def prepare_attack(self, attacker, defender, move_name: str) -> dict:
        """Prepares an attack and returns the ATTACK_ANNOUNCE message."""
        self.pending_attacker = attacker
        self.pending_defender = defender
        self.pending_move = self.build_move_from_name(move_name, attacker)

        attack_message = {
            "message_type": "ATTACK_ANNOUNCE",
            "move_name": move_name,
        }
        return attack_message

    def calculate_and_store(self, attacker, defender) -> dict:
        """Calculates damage and stores it for comparison."""
        state = BattleState(attacker=attacker, defender=defender)
        damage = calculate_damage(state, self.pending_move)

        remaining_hp = defender.current_hp - damage
        if remaining_hp < 0:
            remaining_hp = 0

        self.my_calculation = {"damage": damage, "remaining_hp": remaining_hp}
        return self.my_calculation

    def apply_damage(self, defender, hp_remaining: int):
        """Applies the damage to a pokemon."""
        defender.current_hp = hp_remaining

    def check_game_over(self, defender) -> bool:
        """Checks if a pokemon fainted."""
        if defender is None:
            return False
        return defender.current_hp <= 0

    def create_game_over_message(self) -> dict:
        """Creates a GAME_OVER message."""
        if self.pending_attacker is not None:
            winner_name = self.pending_attacker.name
        else:
            winner_name = "Unknown"

        if self.pending_defender is not None:
            loser_name = self.pending_defender.name
        else:
            loser_name = "Unknown"

        return MessageFactory.game_over(
            winner_name=winner_name,
            loser_name=loser_name,
        )

    def create_calculation_report(self, attacker, defender, damage: int) -> dict:
        """Creates a CALCULATION_REPORT message."""
        defender_hp_remaining = defender.current_hp - damage
        if defender_hp_remaining < 0:
            defender_hp_remaining = 0

        move_type = self.pending_move.move_type.lower()
        type_multiplier = defender.type_multipliers.get(move_type, 1.0)

        status_message = generate_status_message(
            attacker.name, self.pending_move.name, type_multiplier
        )

        return MessageFactory.calculation_report(
            attacker_name=attacker.name,
            move_used=self.pending_move.name,
            attacker_remaining_health=attacker.current_hp,
            damage_dealt=damage,
            defender_hp_remaining=defender_hp_remaining,
            status_message=status_message,
        )

    def get_role_prefix(self) -> str:
        """Returns 'HOST' or 'JOINER' for logging."""
        if self.is_host:
            return "HOST"
        else:
            return "JOINER"
