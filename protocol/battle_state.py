# This file holds the classes for the game

class Pokemon:
    def __init__(self, name, max_hp, current_hp, attack, special_attack, physical_defense, special_defense, type1, type2, type_multipliers, moves):
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
    def __init__(self, name, base_power, category, move_type):
        self.name = name
        self.base_power = base_power
        self.category = category # "physical" or "special"
        self.move_type = move_type

class BattleState:
    def __init__(self, attacker, defender):
        self.attacker = attacker
        self.defender = defender

def calculate_damage(state, move):
    print("Calculating damage for move: " + move.name)
    
    # 1. Get stats
    if move.category == "physical":
        print("It is a physical move.")
        atk = state.attacker.attack
        defense = state.defender.physical_defense
    else:
        print("It is a special move.")
        atk = state.attacker.special_attack
        defense = state.defender.special_defense
        
    print("Attacker stat: " + str(atk))
    print("Defender stat: " + str(defense))
    
    if defense <= 0:
        defense = 1
        
    # 2. Type effectiveness
    # Here we look at the defender's type multipliers
    move_type = move.move_type.lower()
    
    # Default is 1.0 if not found
    multiplier = 1.0
    if move_type in state.defender.type_multipliers:
        multiplier = state.defender.type_multipliers[move_type]
        
    print("Type multiplier: " + str(multiplier))
    
    # 3. The formula
    # Damage = Power * (Atk / Def) * Multiplier
    raw_damage = move.base_power * (atk / defense) * multiplier
    
    final_damage = int(raw_damage)
    
    # Making sure we do at least 1 damage if it's effective
    if final_damage <= 0:
        if multiplier > 0:
            final_damage = 1
            
    return final_damage

def apply_damage(state, damage):
    print("Applying " + str(damage) + " damage to " + state.defender.name)
    new_hp = state.defender.current_hp - damage
    if new_hp < 0:
        new_hp = 0
    state.defender.current_hp = new_hp
