# PokeProtocol - Complete Code Documentation

This document provides a detailed, line-by-line explanation of every file in the PokeProtocol codebase (excluding test files).

---

## Table of Contents

1. [Entry Point: main.py](#1-entry-point-mainpy)
2. [Protocol Layer](#2-protocol-layer)
   - [constants.py](#21-protocolconstantspy)
   - [messages.py](#22-protocolmessagespy)
   - [message_factory.py](#23-protocolmessage_factorypy)
   - [reliability.py](#24-protocolreliabilitypy)
   - [battle_state.py](#25-protocolbattle_statepy)
   - [battle_manager.py](#26-protocolbattle_managerpy)
   - [message_handlers.py](#27-protocolmessage_handlerspy)
   - [pokemon_db.py](#28-protocolpokemon_dbpy)
3. [Peer Layer](#3-peer-layer)
   - [base_peer.py](#31-peersbase_peerpy)
   - [host.py](#32-peershostpy)
   - [joiner.py](#33-peersjoinerpy)
   - [spectator.py](#34-peersspectatorpy)

---

## 1. Entry Point: main.py

This is the file users run to start the application.

### Imports

```python
from protocol.pokemon_db import load_pokemon_db
from peers.host import Host
from peers.joiner import Joiner
from peers.spectator import spectator
```

- `load_pokemon_db`: Function to load all 801 Pokemon from the JSON database
- `Host`, `Joiner`, `spectator`: The three peer classes

### Function: `get_communication_mode()`

```python
def get_communication_mode() -> str:
    print("\nChoose communication mode:")
    print("  1 = P2P (direct connection - works over internet)")
    print("  2 = Broadcast (local network only)")

    while True:
        try:
            choice = int(input("Enter 1 or 2: "))
            if choice == 1:
                return "P2P"
            elif choice == 2:
                return "BROADCAST"
            else:
                print("Please enter 1 or 2")
        except ValueError:
            print("Please enter a number")
```

**How it works:**

1. Prints the menu options
2. Enters infinite loop (`while True`)
3. Uses `try/except` to catch non-numeric input
4. `int(input(...))` converts user input to integer
5. Returns "P2P" or "BROADCAST" string
6. Loop continues until valid input received

### Function: `get_pokemon_id()`

```python
def get_pokemon_id() -> int:
    print("\nChoose your Pokemon!")
    print("Enter a Pokedex ID from 1 to 801")

    while True:
        try:
            pokemon_id = int(input("Pokedex ID: "))
            if 1 <= pokemon_id <= 801:
                return pokemon_id
            else:
                print("ID must be between 1 and 801")
        except ValueError:
            print("Please enter a number")
```

**How it works:**

1. Similar pattern to `get_communication_mode()`
2. `1 <= pokemon_id <= 801` is Python's chained comparison (equivalent to `pokemon_id >= 1 and pokemon_id <= 801`)
3. Returns valid integer ID

### Function: `get_host_connection_info()`

```python
def get_host_connection_info(comm_mode: str) -> tuple:
    if comm_mode == "P2P":
        print("\nEnter the Host's IP address:")
        host_ip = input("IP: ")
    else:
        host_ip = "255.255.255.255"
        print(f"\nUsing broadcast address: {host_ip}")

    print("Enter the Host's port number:")
    while True:
        try:
            host_port = int(input("Port: "))
            return host_ip, host_port
        except ValueError:
            print("Please enter a valid number")
```

**How it works:**

1. If P2P mode, asks for IP address
2. If BROADCAST mode, uses `255.255.255.255` (broadcast to all)
3. Gets port number with validation
4. Returns tuple of (ip_string, port_int)

### Function: `run_host()`

```python
def run_host(pokemon_database: dict):
    print("\n=== Starting as HOST ===")

    comm_mode = get_communication_mode()
    pokemon_id = get_pokemon_id()

    my_pokemon = pokemon_database[pokemon_id]
    print(f"\nYou chose: {my_pokemon.name}!")

    host = Host(my_pokemon, pokemon_database, comm_mode)
    host.accept()
```

**How it works:**

1. Gets settings from user
2. `pokemon_database[pokemon_id]` retrieves Pokemon object by ID
3. Creates `Host` instance with our Pokemon, the full database, and communication mode
4. Calls `host.accept()` which starts the host and blocks until game ends

### Function: `run_joiner()` and `run_spectator()`

Similar pattern to `run_host()` but creates `Joiner` or `Spectator` objects.

### Function: `main()`

```python
def main():
    print("=" * 50)
    print("       POKEPROTOCOL - Pokemon Battle!")
    print("=" * 50)

    print("\nLoading Pokemon database...")
    pokemon_database = load_pokemon_db()
    print(f"Loaded {len(pokemon_database)} Pokemon!")

    print("\nChoose your role:")
    print("  h = Host (start a new game)")
    print("  j = Joiner (join an existing game)")
    print("  s = Spectator (watch a game)")

    choice = input("\nEnter h, j, or s: ").lower().strip()

    if choice == "h":
        run_host(pokemon_database)
    elif choice == "j":
        run_joiner(pokemon_database)
    elif choice == "s":
        run_spectator(pokemon_database)
    else:
        print(f"Unknown choice: '{choice}'")
```

**How it works:**

1. `"=" * 50` creates string of 50 equals signs
2. `load_pokemon_db()` returns dictionary of Pokemon
3. `len(pokemon_database)` counts entries
4. `.lower().strip()` normalizes input (lowercase, remove whitespace)
5. Routes to appropriate function based on choice

### Entry Point Guard

```python
if __name__ == "__main__":
    main()
```

**How it works:**

- `__name__` is `"__main__"` when file is run directly
- `__name__` is the module name when imported
- This prevents `main()` from running when file is imported

---

## 2. Protocol Layer

### 2.1 protocol/constants.py

Defines all constant values used throughout the codebase.

### Class: `MessageType`

```python
class MessageType:
    HANDSHAKE_REQUEST = "HANDSHAKE_REQUEST"
    HANDSHAKE_RESPONSE = "HANDSHAKE_RESPONSE"
    # ... more constants
```

**How it works:**

- Class with class-level attributes (not instance attributes)
- Each attribute is a string constant
- Access via `MessageType.HANDSHAKE_REQUEST`
- Using a class instead of plain strings prevents typos (IDE autocomplete)

### Class: `ContentType`

```python
class ContentType:
    TEXT = "TEXT"
    STICKER = "STICKER"
```

**How it works:**

- Same pattern as `MessageType`
- Used for CHAT_MESSAGE content types

### Class: `CommunicationMode`

```python
class CommunicationMode:
    P2P = "P2P"
    BROADCAST = "BROADCAST"
```

### Protocol Constants

```python
ACK_TIMEOUT_SECONDS = 0.5  # 500 milliseconds
MAX_RETRIES = 3

DEFAULT_SPECIAL_ATTACK_USES = 5
DEFAULT_SPECIAL_DEFENSE_USES = 5
BOOST_MULTIPLIER = 1.5
```

**How it works:**

- Module-level constants
- `0.5` seconds = 500 milliseconds
- These values come from the RFC specification

---

### 2.2 protocol/messages.py

Converts Python dictionaries to text strings and back.

### Function: `encode_message()`

```python
def encode_message(message_dict: dict) -> str:
    # Check for required field
    if "message_type" not in message_dict:
        print("Error: Cannot encode message - no 'message_type' found!")
        print(f"The message was: {message_dict}")
        return None

    # Build the message line by line
    lines = []

    for key in message_dict:
        value = message_dict[key]
        line = key + ": " + str(value)
        lines.append(line)

    # Join all lines with newlines
    full_message = "\n".join(lines)

    return full_message
```

**Step-by-step:**

1. **Validation:**

   ```python
   if "message_type" not in message_dict:
   ```

   - `in` operator checks if key exists in dictionary
   - All valid messages must have `message_type`

2. **Build lines:**

   ```python
   lines = []
   for key in message_dict:
       value = message_dict[key]
       line = key + ": " + str(value)
       lines.append(line)
   ```

   - `for key in dict` iterates over keys
   - `str(value)` converts any type to string (handles integers, etc.)
   - Each line format: `"key: value"`

3. **Join:**
   ```python
   full_message = "\n".join(lines)
   ```
   - `"\n".join(list)` puts newline between each element
   - Example: `["a", "b", "c"]` → `"a\nb\nc"`

**Example:**

```python
encode_message({"message_type": "ACK", "ack_number": 5})
# Returns: "message_type: ACK\nack_number: 5"
```

### Function: `decode_message()`

```python
def decode_message(raw_text: str) -> dict:
    result = {}

    lines = raw_text.split("\n")

    for line in lines:
        line = line.strip()

        if line == "":
            continue

        parts = line.split(":")

        if len(parts) < 2:
            continue

        key = parts[0].strip()
        value = ":".join(parts[1:]).strip()

        result[key] = value

    if "message_type" not in result:
        print("Warning: Decoded message has no 'message_type' field")

    return result
```

**Step-by-step:**

1. **Split into lines:**

   ```python
   lines = raw_text.split("\n")
   ```

   - `"a\nb\nc".split("\n")` → `["a", "b", "c"]`

2. **Process each line:**

   ```python
   line = line.strip()
   if line == "":
       continue
   ```

   - `.strip()` removes leading/trailing whitespace
   - `continue` skips to next iteration (skip empty lines)

3. **Split key and value:**

   ```python
   parts = line.split(":")
   if len(parts) < 2:
       continue
   ```

   - `"key: value".split(":")` → `["key", " value"]`
   - Need at least 2 parts for valid key:value

4. **Handle colons in value:**

   ```python
   key = parts[0].strip()
   value = ":".join(parts[1:]).strip()
   ```

   - `parts[0]` is the key
   - `parts[1:]` is everything after first colon (handles values with colons)
   - Example: `"time: 10:30:00"` → key=`"time"`, value=`"10:30:00"`

5. **Store in dictionary:**
   ```python
   result[key] = value
   ```

---

### 2.3 protocol/message_factory.py

Factory class for creating protocol messages.

### Import and Class Definition

```python
from protocol.constants import (
    MessageType,
    ContentType,
    DEFAULT_SPECIAL_ATTACK_USES,
    DEFAULT_SPECIAL_DEFENSE_USES,
)

class MessageFactory:
```

### Static Methods

All methods use `@staticmethod` decorator:

```python
@staticmethod
def handshake_request() -> dict:
    return {"message_type": MessageType.HANDSHAKE_REQUEST}
```

**How `@staticmethod` works:**

- Method doesn't need `self` parameter
- Can be called without creating an instance: `MessageFactory.handshake_request()`
- Used because these methods don't access instance data

### Example: `attack_announce()`

```python
@staticmethod
def attack_announce(move_name: str) -> dict:
    return {"message_type": MessageType.ATTACK_ANNOUNCE, "move_name": move_name}
```

**How it works:**

1. Takes `move_name` parameter
2. Returns dictionary with correct structure
3. Uses `MessageType.ATTACK_ANNOUNCE` constant (prevents typos)

### Example: `calculation_report()`

```python
@staticmethod
def calculation_report(
    attacker_name: str,
    move_used: str,
    attacker_remaining_health: int,
    damage_dealt: int,
    defender_hp_remaining: int,
    status_message: str,
) -> dict:
    message = {
        "message_type": MessageType.CALCULATION_REPORT,
        "attacker": attacker_name,
        "move_used": move_used,
        "remaining_health": str(attacker_remaining_health),
        "damage_dealt": str(damage_dealt),
        "defender_hp_remaining": str(defender_hp_remaining),
        "status_message": status_message,
    }
    return message
```

**How it works:**

1. Takes all required fields as parameters
2. Converts integers to strings (protocol uses text format)
3. Returns properly structured dictionary

---

### 2.4 protocol/reliability.py

Implements reliable message delivery over UDP.

### Configuration Constants

```python
TIMEOUT_SECONDS = 0.5
MAX_RETRY_ATTEMPTS = 3
QUEUE_CHECK_INTERVAL = 0.1
```

### Class: `ReliableChannel`

```python
class ReliableChannel:
    def __init__(self, sock, ack_queue: Queue):
        self.sock = sock
        self.ack_queue = ack_queue
        self.sequence_number = 1
        self.send_lock = threading.Lock()
```

**Attributes:**

- `sock`: The UDP socket to send messages through
- `ack_queue`: Queue where listener puts ACK messages
- `sequence_number`: Next sequence number to use (starts at 1)
- `send_lock`: Threading lock to prevent concurrent sends

### Method: `send_with_ack()`

```python
def send_with_ack(self, message: dict, destination_address: tuple) -> bool:
    with self.send_lock:
        return self._send_message_with_retries(message, destination_address)
```

**How it works:**

1. `with self.send_lock:` acquires the lock (releases automatically when done)
2. Only one thread can be inside this block at a time
3. Calls private method to do actual work

### Method: `_send_message_with_retries()`

```python
def _send_message_with_retries(self, message: dict, destination_address: tuple) -> bool:
    # Step 1: Add sequence number
    current_sequence = self.sequence_number
    message["sequence_number"] = str(current_sequence)

    # Step 2: Encode and convert to bytes
    message_as_string = encode_message(message)
    message_as_bytes = message_as_string.encode("utf-8")

    # Step 3: Try up to MAX_RETRY_ATTEMPTS times
    for attempt_number in range(1, MAX_RETRY_ATTEMPTS + 1):
        print(f"Attempt {attempt_number}: Sending message with seq={current_sequence}")

        # Send the message
        self.sock.sendto(message_as_bytes, destination_address)

        # Wait for ACK
        ack_was_received = self._wait_for_ack(current_sequence)

        if ack_was_received:
            self.sequence_number = self.sequence_number + 1
            print("ACK received - message delivered successfully!")
            return True
        else:
            print(f"Timeout - no ACK received for seq={current_sequence}")

    print(f"FAILED: Could not deliver message after {MAX_RETRY_ATTEMPTS} attempts")
    return False
```

**Step-by-step:**

1. **Add sequence number:**

   ```python
   message["sequence_number"] = str(current_sequence)
   ```

   - Modifies the message dictionary in place
   - Converts to string for protocol format

2. **Encode message:**

   ```python
   message_as_string = encode_message(message)
   message_as_bytes = message_as_string.encode("utf-8")
   ```

   - `encode_message()` converts dict to string
   - `.encode("utf-8")` converts string to bytes (required for socket)

3. **Send via socket:**

   ```python
   self.sock.sendto(message_as_bytes, destination_address)
   ```

   - `sendto(data, address)` sends UDP datagram
   - `address` is tuple like `("192.168.1.100", 5001)`

4. **Retry loop:**

   ```python
   for attempt_number in range(1, MAX_RETRY_ATTEMPTS + 1):
   ```

   - `range(1, 4)` → `[1, 2, 3]` (3 attempts)

5. **Success handling:**
   ```python
   if ack_was_received:
       self.sequence_number = self.sequence_number + 1
       return True
   ```
   - Increment sequence for next message
   - Return True to indicate success

### Method: `_wait_for_ack()`

```python
def _wait_for_ack(self, expected_sequence_number: int) -> bool:
    start_time = time.time()
    messages_to_put_back = []

    while True:
        # Check timeout
        elapsed_time = time.time() - start_time
        if elapsed_time >= TIMEOUT_SECONDS:
            self._put_messages_back(messages_to_put_back)
            return False

        # Try to get message from queue
        message = self._get_message_from_queue()

        if message is None:
            continue

        # Check if it's our ACK
        if self._is_matching_ack(message, expected_sequence_number):
            self._put_messages_back(messages_to_put_back)
            return True
        else:
            messages_to_put_back.append(message)
```

**Step-by-step:**

1. **Track time:**

   ```python
   start_time = time.time()
   elapsed_time = time.time() - start_time
   ```

   - `time.time()` returns current time in seconds (float)
   - Difference gives elapsed time

2. **Queue handling:**

   ```python
   message = self._get_message_from_queue()
   if message is None:
       continue
   ```

   - `_get_message_from_queue()` returns None if queue empty
   - `continue` restarts the loop

3. **Message borrowing:**
   ```python
   messages_to_put_back.append(message)
   ```
   - If we pull out wrong message, save it
   - Put back when done so other code can use it

### Method: `_is_matching_ack()`

```python
def _is_matching_ack(self, message: dict, expected_sequence_number: int) -> bool:
    message_type = message.get("message_type", "")
    if message_type != "ACK":
        return False

    ack_number_string = message.get("ack_number", "-1")
    ack_number = int(ack_number_string)

    return ack_number == expected_sequence_number
```

**How it works:**

1. `dict.get(key, default)` returns value or default if missing
2. Check if message type is "ACK"
3. Parse ack_number and compare

---

### 2.5 protocol/battle_state.py

Pokemon game mechanics.

### Global RNG Setup

```python
import random

_battle_rng = random.Random()

def initialize_battle_rng(seed: int):
    global _battle_rng
    _battle_rng = random.Random(seed)
    print(f"[RNG] Initialized with seed: {seed}")

def get_battle_rng() -> random.Random:
    return _battle_rng
```

**How it works:**

1. **Global variable:**

   ```python
   _battle_rng = random.Random()
   ```

   - `_` prefix indicates "private" (convention, not enforced)
   - Creates a Random instance

2. **Initialize with seed:**

   ```python
   global _battle_rng
   _battle_rng = random.Random(seed)
   ```

   - `global` keyword needed to modify module-level variable
   - `random.Random(seed)` creates seeded RNG
   - Same seed → same "random" sequence

3. **Getter:**
   - Returns the shared RNG instance
   - Both peers use same seed → same results

### Enum: `BattlePhase`

```python
from enum import Enum

class BattlePhase(Enum):
    WAITING_FOR_MOVE = "WAITING_FOR_MOVE"
    PROCESSING_TURN = "PROCESSING_TURN"
```

**How Enum works:**

- `Enum` is a special class for named constants
- `BattlePhase.WAITING_FOR_MOVE` is an enum member
- `BattlePhase.WAITING_FOR_MOVE.value` returns `"WAITING_FOR_MOVE"`
- Can compare: `phase == BattlePhase.WAITING_FOR_MOVE`

### Type Sets

```python
PHYSICAL_TYPES = {
    "normal", "fighting", "flying", "poison", "ground",
    "rock", "bug", "ghost", "steel",
}

SPECIAL_TYPES = {
    "fire", "water", "grass", "electric", "psychic",
    "ice", "dragon", "dark", "fairy",
}
```

**How sets work:**

- `{...}` creates a set (unordered, unique elements)
- `"fire" in SPECIAL_TYPES` → `True` (O(1) lookup)
- Used to categorize move types

### Function: `get_damage_category()`

```python
def get_damage_category(move_type: str) -> str:
    move_type_lower = move_type.lower()

    if move_type_lower in PHYSICAL_TYPES:
        return "physical"
    else:
        return "special"
```

**How it works:**

1. `.lower()` converts to lowercase (handles "Fire" vs "fire")
2. `in` operator checks set membership
3. Returns category string

### Class: `Pokemon`

```python
class Pokemon:
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
```

**How it works:**

- `__init__` is constructor, called when creating instance
- `self` refers to the instance being created
- Each `self.x = x` stores parameter as instance attribute
- `type_multipliers` is dict like `{"electric": 2.0, "ground": 0.0}`

### Class: `Move`

```python
class Move:
    def __init__(self, name: str, base_power: int, category: str, move_type: str):
        self.name = name
        self.base_power = base_power
        self.category = category  # "physical" or "special"
        self.move_type = move_type
```

### Class: `BattleState`

```python
class BattleState:
    def __init__(self, attacker: Pokemon, defender: Pokemon):
        self.attacker = attacker
        self.defender = defender
```

**How it works:**

- Simple container for attacker/defender pair
- Used in damage calculation

### Function: `calculate_damage()`

```python
def calculate_damage(
    state: BattleState,
    move: Move,
    attack_boost: float = 1.0,
    defense_boost: float = 1.0
) -> int:
    print(f"Calculating damage for move: {move.name}")

    # Step 1: Get correct stats based on move category
    if move.category == "physical":
        print("It is a physical move.")
        attacker_stat = state.attacker.attack
        defender_stat = state.defender.physical_defense
    else:
        print("It is a special move.")
        attacker_stat = state.attacker.special_attack
        defender_stat = state.defender.special_defense

    # Step 2: Apply boosts
    attacker_stat = attacker_stat * attack_boost
    defender_stat = defender_stat * defense_boost

    # Step 3: Ensure defense is at least 1
    if defender_stat <= 0:
        defender_stat = 1

    # Step 4: Get type effectiveness
    move_type_lower = move.move_type.lower()
    type_multiplier = 1.0
    if move_type_lower in state.defender.type_multipliers:
        type_multiplier = state.defender.type_multipliers[move_type_lower]

    print(f"Type multiplier: {type_multiplier}")

    # Step 5: Calculate damage
    raw_damage = (attacker_stat * type_multiplier) / defender_stat
    final_damage = int(round(raw_damage))

    # Step 6: Minimum 1 damage if move is effective
    if final_damage <= 0 and type_multiplier > 0:
        final_damage = 1

    return final_damage
```

**Step-by-step explanation:**

1. **Choose stats:**

   - Physical moves use Attack vs Defense
   - Special moves use Special Attack vs Special Defense

2. **Apply boosts:**

   ```python
   attacker_stat = attacker_stat * attack_boost
   ```

   - `attack_boost = 1.5` means 50% increase
   - Default is `1.0` (no change)

3. **Type effectiveness:**

   ```python
   type_multiplier = state.defender.type_multipliers.get(move_type_lower, 1.0)
   ```

   - Look up multiplier from defender's type chart
   - 2.0 = super effective, 0.5 = not effective, 0.0 = immune

4. **Formula:**

   ```python
   raw_damage = (attacker_stat * type_multiplier) / defender_stat
   ```

   - Higher attack → more damage
   - Higher defense → less damage
   - Type multiplier scales result

5. **Rounding:**
   ```python
   final_damage = int(round(raw_damage))
   ```
   - `round()` rounds to nearest integer
   - `int()` ensures integer type

### Function: `generate_status_message()`

```python
def generate_status_message(
    attacker_name: str,
    move_name: str,
    type_multiplier: float
) -> str:
    base_message = f"{attacker_name} used {move_name}!"

    if type_multiplier == 0:
        return f"{base_message} It had no effect..."
    elif type_multiplier < 1:
        return f"{base_message} It's not very effective..."
    elif type_multiplier > 1:
        return f"{base_message} It was super effective!"
    else:
        return base_message
```

**How it works:**

- Uses f-strings for string formatting
- Returns different messages based on effectiveness

---

### 2.6 protocol/battle_manager.py

Manages battle flow and state.

### Class: `BattleManager`

```python
class BattleManager:
    def __init__(self, is_host: bool = True):
        self.is_host = is_host
        self.battle_phase = None
        self.is_my_turn = is_host  # Host goes first!

        # Current turn info
        self.pending_move = None
        self.pending_attacker = None
        self.pending_defender = None
        self.my_calculation = None

        # Stat boosts
        self.special_attack_uses = DEFAULT_SPECIAL_ATTACK_USES   # 5
        self.special_defense_uses = DEFAULT_SPECIAL_DEFENSE_USES  # 5
        self.opp_special_attack_uses = DEFAULT_SPECIAL_ATTACK_USES
        self.opp_special_defense_uses = DEFAULT_SPECIAL_DEFENSE_USES

        # Boost flags for current turn
        self.use_special_attack_boost = False
        self.use_special_defense_boost = False
        self.defense_boost_armed = False
```

**Key attributes:**

- `is_my_turn`: `True` if it's our turn
- `pending_*`: Info about current attack being processed
- `special_*_uses`: How many boosts remaining
- `*_boost` flags: Whether boost is active this turn

### Method: `switch_turn()`

```python
def switch_turn(self):
    self.is_my_turn = not self.is_my_turn
    self.battle_phase = BattlePhase.WAITING_FOR_MOVE
    self.reset_turn_state()
```

**How it works:**

1. `not self.is_my_turn` toggles boolean (True→False, False→True)
2. Reset to WAITING_FOR_MOVE phase
3. Clear all turn-specific data

### Method: `use_special_attack()`

```python
def use_special_attack(self) -> bool:
    if self.special_attack_uses <= 0:
        print(f"[{role}] No Special Attack boosts remaining!")
        return False

    self.special_attack_uses = self.special_attack_uses - 1
    self.use_special_attack_boost = True

    print(f"[{role}] Using Special Attack boost! ({self.special_attack_uses} remaining)")
    return True
```

**How it works:**

1. Check if uses remaining
2. Decrement counter
3. Set flag for damage calculation
4. Return success/failure

### Method: `arm_defense_boost()`

```python
def arm_defense_boost(self) -> bool:
    if self.special_defense_uses <= 0:
        return False

    self.defense_boost_armed = True
    return True
```

**How it works:**

- Sets `defense_boost_armed = True`
- Does NOT consume the use yet
- Use is consumed when attack actually comes in

### Method: `consume_armed_defense_boost()`

```python
def consume_armed_defense_boost(self) -> bool:
    if not self.defense_boost_armed:
        return False

    if self.special_defense_uses <= 0:
        self.defense_boost_armed = False
        return False

    self.special_defense_uses = self.special_defense_uses - 1
    self.use_special_defense_boost = True
    self.defense_boost_armed = False

    return True
```

**How it works:**

1. Check if boost was armed
2. Check if uses remaining
3. Consume the use
4. Activate the boost
5. Clear armed flag

### Method: `create_calculation_report()`

```python
def create_calculation_report(self, attacker, defender, damage: int) -> dict:
    defender_hp_remaining = defender.current_hp - damage
    if defender_hp_remaining < 0:
        defender_hp_remaining = 0

    move_type = self.pending_move.move_type.lower()
    type_multiplier = defender.type_multipliers.get(move_type, 1.0)

    status_message = generate_status_message(
        attacker.name,
        self.pending_move.name,
        type_multiplier
    )

    return MessageFactory.calculation_report(
        attacker_name=attacker.name,
        move_used=self.pending_move.name,
        attacker_remaining_health=attacker.current_hp,
        damage_dealt=damage,
        defender_hp_remaining=defender_hp_remaining,
        status_message=status_message,
    )
```

**How it works:**

1. Calculate defender's HP after damage
2. Get type effectiveness for status message
3. Generate status message
4. Use MessageFactory to create properly formatted message

---

### 2.7 protocol/message_handlers.py

Functions that process each message type.

### Helper Function: `get_role_name()`

```python
def get_role_name(is_host: bool) -> str:
    if is_host:
        return "HOST"
    else:
        return "JOINER"
```

### Function: `handle_battle_setup()`

```python
def handle_battle_setup(kv: dict, peer, is_host: bool = True):
    role = get_role_name(is_host)

    # Get Pokemon name
    pokemon_name = kv.get("pokemon_name")
    if not pokemon_name:
        print(f"[{role}] Error: BATTLE_SETUP missing pokemon_name")
        return None

    # Look up in database
    opponent_pokemon = peer.db.get(pokemon_name.lower())
    if not opponent_pokemon:
        print(f"[{role}] Error: Unknown Pokemon '{pokemon_name}'")
        return None

    # Store opponent's Pokemon
    peer.opp_mon = opponent_pokemon
    print(f"[{role}] Opponent chose {opponent_pokemon.name}")

    # Parse stat boosts
    stat_boosts_str = kv.get("stat_boosts", "")
    if stat_boosts_str:
        sp_atk_uses, sp_def_uses = parse_stat_boosts(stat_boosts_str)
        peer.battle_manager.set_opponent_stat_boosts(sp_atk_uses, sp_def_uses)

    # Transition to battle phase
    peer.battle_manager.battle_phase = BattlePhase.WAITING_FOR_MOVE

    return None
```

**Step-by-step:**

1. Get Pokemon name from message
2. Look up in database (lowercase for consistent lookup)
3. Store as `peer.opp_mon`
4. Parse and store opponent's stat boost allocation
5. Set battle phase to WAITING_FOR_MOVE

### Function: `handle_attack_announce()`

```python
def handle_attack_announce(kv: dict, peer, is_host: bool = True):
    role = get_role_name(is_host)
    move_name = kv.get("move_name", "")

    # Opponent is attacking us
    attacker = peer.opp_mon      # Their Pokemon
    defender = peer.pokemon       # Our Pokemon

    if attacker is None or defender is None:
        return None, None

    # Store attack info
    battle_manager = peer.battle_manager
    battle_manager.pending_attacker = attacker
    battle_manager.pending_defender = defender

    # Create Move object
    move_type = attacker.type1.lower()
    damage_category = get_damage_category(move_type)
    battle_manager.pending_move = Move(
        name=move_name,
        base_power=1,
        category=damage_category,
        move_type=move_type,
    )

    # Create DEFENSE_ANNOUNCE
    defense_message = MessageFactory.defense_announce()

    # Set phase
    battle_manager.battle_phase = BattlePhase.PROCESSING_TURN

    # Check for armed defense boost
    battle_manager.consume_armed_defense_boost()
    defense_multiplier = battle_manager.get_defense_multiplier()

    # Calculate damage
    battle_state = BattleState(attacker=attacker, defender=defender)
    damage = calculate_damage(
        battle_state,
        battle_manager.pending_move,
        attack_boost=1.0,
        defense_boost=defense_multiplier,
    )

    # Store calculation
    defender_hp_remaining = max(0, defender.current_hp - damage)
    battle_manager.my_calculation = {
        "damage": damage,
        "remaining_hp": defender_hp_remaining,
    }

    # Create CALCULATION_REPORT
    calculation_report = battle_manager.create_calculation_report(
        attacker, defender, damage
    )

    return defense_message, calculation_report
```

**Key points:**

1. We're the defender (they're attacking us)
2. Create Move from attacker's type
3. Check if we armed a defense boost
4. Calculate damage with our defense boost
5. Return both DEFENSE_ANNOUNCE and CALCULATION_REPORT

### Function: `handle_calculation_report()`

```python
def handle_calculation_report(kv: dict, peer, is_host: bool = True):
    role = get_role_name(is_host)
    battle_manager = peer.battle_manager

    # Parse their calculation
    reported_damage = int(kv.get("damage_dealt", "0"))
    reported_hp_remaining = int(kv.get("defender_hp_remaining", "0"))

    # Get our calculation
    if not battle_manager.my_calculation:
        return None, None, False

    our_damage = battle_manager.my_calculation["damage"]
    our_hp_remaining = battle_manager.my_calculation["remaining_hp"]

    # Compare
    damage_matches = (our_damage == reported_damage)
    hp_matches = (our_hp_remaining == reported_hp_remaining)

    if damage_matches and hp_matches:
        # Match! Send CALCULATION_CONFIRM
        confirm_message = MessageFactory.calculation_confirm()

        # Apply damage
        if battle_manager.pending_defender:
            battle_manager.pending_defender.current_hp = our_hp_remaining

        # Check game over
        if our_hp_remaining <= 0 and battle_manager.pending_defender:
            game_over_message = battle_manager.create_game_over_message()
            return confirm_message, game_over_message, True

        return confirm_message, None, False
    else:
        # Mismatch! Send RESOLUTION_REQUEST
        resolution_message = MessageFactory.resolution_request(
            attacker_name=battle_manager.pending_attacker.name,
            move_used=battle_manager.pending_move.name,
            damage_dealt=our_damage,
            defender_hp_remaining=our_hp_remaining,
        )
        return resolution_message, None, False
```

**Return value:**

- `(response_msg, game_over_msg_or_None, should_stop)`
- First message is always sent
- Game over message only if battle ends
- Boolean indicates if battle should stop

### Function: `handle_calculation_confirm()`

```python
def handle_calculation_confirm(kv: dict, peer, is_host: bool = True):
    battle_manager = peer.battle_manager

    # Get our stored calculation
    our_damage = battle_manager.my_calculation["damage"]
    our_hp_remaining = battle_manager.my_calculation["remaining_hp"]

    # Apply damage
    if battle_manager.pending_defender:
        battle_manager.pending_defender.current_hp = our_hp_remaining

    # Check game over
    if our_hp_remaining <= 0:
        return False  # Game over

    # Switch turns
    battle_manager.switch_turn()

    return True  # Game continues
```

**How it works:**

1. Use our stored calculation (both peers agreed)
2. Apply damage to defender
3. Check if defender fainted
4. Switch turns if game continues

---

### 2.8 protocol/pokemon_db.py

Loads Pokemon data from JSON file.

```python
import json
from protocol.battle_state import Pokemon

def load_pokemon_db() -> dict:
    with open("pokemon_data.json", "r") as f:
        data = json.load(f)

    db = {}
    for entry in data:
        pokemon = Pokemon(
            name=entry["name"],
            max_hp=entry["hp"],
            current_hp=entry["hp"],
            attack=entry["attack"],
            special_attack=entry["sp_attack"],
            physical_defense=entry["defense"],
            special_defense=entry["sp_defense"],
            type1=entry["type1"],
            type2=entry.get("type2", ""),
            type_multipliers=entry.get("type_multipliers", {}),
            moves=entry.get("moves", []),
        )

        # Index by ID and name
        db[entry["id"]] = pokemon
        db[pokemon.name.lower()] = pokemon

    return db
```

**Step-by-step:**

1. **Open JSON file:**

   ```python
   with open("pokemon_data.json", "r") as f:
       data = json.load(f)
   ```

   - `with` ensures file is closed after
   - `json.load()` parses JSON into Python objects

2. **Create Pokemon objects:**

   ```python
   pokemon = Pokemon(name=entry["name"], ...)
   ```

   - Extract fields from JSON entry
   - `.get("key", default)` provides default if missing

3. **Index by ID and name:**
   ```python
   db[entry["id"]] = pokemon
   db[pokemon.name.lower()] = pokemon
   ```
   - Same Pokemon accessible by ID (integer) or name (lowercase string)

---

## 3. Peer Layer

### 3.1 peers/base_peer.py

Base class with common peer functionality.

### Constructor

```python
class BasePeer:
    def __init__(self, pokemon, db, comm_mode: str, is_host: bool = True):
        # Pokemon and battle info
        self.pokemon = pokemon
        self.opp_mon = None
        self.db = db
        self.is_host = is_host
        self.name = ""
        self.comm_mode = comm_mode

        # Socket setup
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Message handling
        self.ack_queue = queue.Queue()
        self.kv_messages = []
        self.lock = threading.Lock()
        self.last_processed_sequence = 0
        self.ack = None

        # State flags
        self.running = False
        self.listening = True

        # Components
        self.reliability = ReliableChannel(self.sock, self.ack_queue)
        self.battle_manager = BattleManager(is_host=is_host)
        self.remote_addr = None
        self.seed = None
```

**Socket creation:**

```python
self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
```

- `AF_INET`: IPv4 addresses
- `SOCK_DGRAM`: UDP (datagram) socket

**Socket options:**

```python
self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
```

- `SO_BROADCAST`: Allow sending to broadcast address
- `SO_REUSEADDR`: Allow reusing address (helpful when restarting)

### Method: `listen_loop()`

```python
def listen_loop(self):
    try:
        self.sock.settimeout(None)
    except OSError:
        return

    while self.listening:
        try:
            raw_message, sender_address = self.sock.recvfrom(1024)
        except socket.timeout:
            continue
        except OSError:
            break

        # Decode message
        message_string = raw_message.decode("utf-8")
        message_dict = decode_message(message_string)

        # Print (unless ACK)
        if message_dict.get("message_type") != MessageType.ACK:
            print(f"\n{message_string}")

        # Put in ACK queue
        self.ack_queue.put(message_dict)

        # Handle sequence/ACK
        is_duplicate = self.handle_sequence_and_ack(message_dict, sender_address)
        if is_duplicate:
            continue

        # Store and process
        self.store_message(message_dict)
        self.process_message(message_dict, sender_address)
```

**Key points:**

1. **Receive data:**

   ```python
   raw_message, sender_address = self.sock.recvfrom(1024)
   ```

   - `recvfrom(1024)` receives up to 1024 bytes
   - Returns (data, address) tuple
   - Blocks until data arrives

2. **Decode:**

   ```python
   message_string = raw_message.decode("utf-8")
   message_dict = decode_message(message_string)
   ```

   - Convert bytes to string
   - Parse string to dictionary

3. **ACK queue:**

   ```python
   self.ack_queue.put(message_dict)
   ```

   - Put all messages in queue
   - Reliability layer checks this for ACKs

4. **Duplicate detection:**
   ```python
   if is_duplicate:
       continue
   ```
   - Skip already-processed messages

### Method: `handle_sequence_and_ack()`

```python
def handle_sequence_and_ack(self, message: dict, sender_address: tuple) -> bool:
    if "sequence_number" not in message:
        return False

    incoming_sequence = int(message["sequence_number"])

    # Send ACK
    ack_message = MessageFactory.ack(incoming_sequence)
    ack_encoded = encode_message(ack_message)
    self.sock.sendto(ack_encoded.encode("utf-8"), sender_address)

    # Check duplicate
    if incoming_sequence <= self.last_processed_sequence:
        return True  # Duplicate

    self.last_processed_sequence = incoming_sequence
    return False  # New message
```

**How it works:**

1. Check if message has sequence number
2. Always send ACK (even for duplicates)
3. Compare to last processed sequence
4. Update sequence tracker

### Method: `process_message()`

```python
def process_message(self, message: dict, sender_address: tuple):
    message_type = message.get("message_type")

    if message_type == MessageType.BATTLE_SETUP:
        message_handlers.handle_battle_setup(message, self, is_host=self.is_host)
        self._on_battle_setup(message)

    elif message_type == MessageType.ATTACK_ANNOUNCE:
        defense_msg, calculation_report_msg = message_handlers.handle_attack_announce(
            message, self, is_host=self.is_host
        )

        if defense_msg and calculation_report_msg:
            def send_responses():
                self.reliability.send_with_ack(defense_msg, self.remote_addr)
                self.reliability.send_with_ack(calculation_report_msg, self.remote_addr)

            background_thread = threading.Thread(target=send_responses, daemon=True)
            background_thread.start()

    # ... more message types ...
```

**Key patterns:**

1. **Route by type:**

   ```python
   if message_type == MessageType.BATTLE_SETUP:
       ...
   elif message_type == MessageType.ATTACK_ANNOUNCE:
       ...
   ```

2. **Background sending:**

   ```python
   def send_responses():
       self.reliability.send_with_ack(defense_msg, self.remote_addr)

   background_thread = threading.Thread(target=send_responses, daemon=True)
   background_thread.start()
   ```

   - `threading.Thread(target=func)` creates thread that runs `func`
   - `daemon=True` means thread dies when main program exits
   - `.start()` begins execution

### Method: `perform_attack()`

```python
def perform_attack(self) -> bool:
    bm = self.battle_manager

    # Validation
    if not bm.is_my_turn:
        print("It's not your turn!")
        return False

    if bm.battle_phase != BattlePhase.WAITING_FOR_MOVE:
        print("Cannot attack right now")
        return False

    if not self.opp_mon:
        print("Opponent not set up")
        return False

    # Choose move
    print(f"Your Pokemon: {self.pokemon.name}")
    if not self.pokemon.moves:
        move_name = "BasicMove"
    else:
        print("Available moves:")
        for index, move in enumerate(self.pokemon.moves, start=1):
            print(f"  {index}. {move}")

        choice = input("Choose a move number: ")
        try:
            index = int(choice) - 1
            move_name = self.pokemon.moves[index]
        except:
            move_name = self.pokemon.moves[0]

    # Ask about boost
    if bm.special_attack_uses > 0:
        use_boost = input("Use Special Attack boost? (y/n): ")
        if use_boost.lower().strip() == "y":
            bm.use_special_attack()

    # Send attack
    attack_message = bm.prepare_attack(self.pokemon, self.opp_mon, move_name)
    self.reliability.send_with_ack(attack_message, self.remote_addr)

    return True
```

**Key points:**

1. Validate it's our turn and right phase
2. Display and select move
3. Offer attack boost option
4. Create and send ATTACK_ANNOUNCE

### Method: `chat()`

```python
def chat(self):
    bm = self.battle_manager

    # Show status
    print(f"\n--- Status ---")
    print(f"  Special Attack boosts: {bm.special_attack_uses}")
    print(f"  Special Defense boosts: {bm.special_defense_uses}")

    # Get command
    user_input = input("\nEnter command: ")
    command = user_input.strip().lower()

    # Handle commands
    if command == "!attack":
        self.perform_attack()

    elif command == "!defend":
        if bm.is_my_turn:
            print("Can only defend when waiting for opponent")
        else:
            bm.arm_defense_boost()

    elif command == "!chat":
        text = input("Type your message: ")
        self.send_chat_message(text)

    elif command == "!sticker":
        sticker = input("Enter sticker data: ")
        self.send_sticker_message(sticker)
```

---

### 3.2 peers/host.py

Host-specific implementation.

### Constructor

```python
class Host(BasePeer):
    def __init__(self, pokemon, db, comm_mode: str):
        super().__init__(pokemon, db, comm_mode, is_host=True)

        self.host_address = ""
        self.seed = 0
        self.request_queue = queue.Queue()
        self.battle_setup_done = False

        self.spectator_connected = False
        self.spectator_address = None
```

**Key points:**

- `super().__init__(...)` calls parent class constructor
- `is_host=True` sets host-specific behavior
- `request_queue` holds incoming connection requests

### Method: `accept()`

```python
def accept(self):
    self.name = input("Enter your name: ")

    # Get address
    if self.comm_mode == "P2P":
        self.host_address = input("Enter your IP address: ")
    else:
        self.host_address = "0.0.0.0"

    # Get port
    port = 5000
    while port <= 5000:
        port = int(input("Port (above 5000): "))

    # Bind socket
    self.sock.bind((self.host_address, port))
    print(f"Listening on port {port}")

    # Start accept loop
    self.running = True
    accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
    accept_thread.start()

    # Main loop - process connection requests
    while True:
        if not self.request_queue.empty():
            request_message, joiner_address = self.request_queue.get()

            choice = input("Accept connection? (Y/N): ").upper()
            if choice != "Y":
                continue

            # Store address
            self.remote_addr = joiner_address
            self.running = False

            # Get seed
            seed = int(input("Enter random seed: "))
            self.seed = seed

            # Send handshake response
            handshake_response = MessageFactory.handshake_response(seed)
            encoded = encode_message(handshake_response)
            self.sock.sendto(encoded.encode("utf-8"), self.remote_addr)

            # Initialize RNG
            self.initialize_rng(seed)

            # Start listener
            listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
            listener_thread.start()

            # Chat loop
            while True:
                self.chat()
```

**Key steps:**

1. Bind socket to address:port
2. Start accept loop in background
3. Wait for and process connection requests
4. Send handshake with seed
5. Start listener and chat loops

### Method: `_accept_loop()`

```python
def _accept_loop(self):
    while self.running:
        try:
            raw_message, sender_address = self.sock.recvfrom(1024)
        except OSError:
            break

        message_string = raw_message.decode("utf-8")
        message_dict = decode_message(message_string)

        if message_dict.get("message_type") == "HANDSHAKE_REQUEST":
            self.request_queue.put((message_string, sender_address))
```

**How it works:**

- Runs in background thread
- Only processes HANDSHAKE_REQUEST
- Puts requests in queue for main thread

### Method: `_on_battle_setup()`

```python
def _on_battle_setup(self, message: dict):
    if self.battle_setup_done:
        return
    if self.remote_addr is None:
        return

    our_battle_setup = MessageFactory.battle_setup(
        communication_mode=self.comm_mode,
        pokemon_name=self.pokemon.name,
    )

    self.battle_setup_done = True

    def send_battle_setup():
        self.reliability.send_with_ack(our_battle_setup, self.remote_addr)

    threading.Thread(target=send_battle_setup, daemon=True).start()
```

**How it works:**

- Called after receiving Joiner's BATTLE_SETUP
- Sends our own BATTLE_SETUP in response
- Uses flag to prevent sending twice

---

### 3.3 peers/joiner.py

Joiner-specific implementation.

### Constructor

```python
class Joiner(BasePeer):
    def __init__(self, pokemon, db, comm_mode: str):
        super().__init__(pokemon, db, comm_mode, is_host=False)
        self.seed = None
```

**Key point:**

- `is_host=False` sets joiner behavior
- `seed = None` until received from host

### Method: `start()`

```python
def start(self, host_ip: str, host_port: int):
    # Bind socket
    if self.comm_mode == "P2P":
        self.sock.bind(("", 0))  # Any port
    else:
        self.sock.bind(("0.0.0.0", host_port))

    self.name = input("Enter your name: ")

    # Start listener
    self.running = True
    listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
    listener_thread.start()

    # Send handshake
    self._send_handshake(host_ip, host_port)
    print("Waiting for Host...")

    # Wait for seed
    while self.seed is None:
        time.sleep(0.5)

    # Send battle setup
    self._send_battle_setup()

    # Chat loop
    while True:
        self.chat()
```

**Key steps:**

1. Bind socket (any port in P2P mode)
2. Start listener thread
3. Send HANDSHAKE_REQUEST
4. Wait for seed (set by `process_message`)
5. Send BATTLE_SETUP
6. Enter chat loop

### Method: `process_message()` (override)

```python
def process_message(self, message: dict, sender_address: tuple):
    # Check for seed
    if "seed" in message and self.seed is None:
        seed_value = int(message["seed"])
        self.seed = seed_value
        self.initialize_rng(seed_value)

    # Call parent handler
    super().process_message(message, sender_address)
```

**How it works:**

- Check if message contains seed
- If so, extract and initialize RNG
- Then call parent's process_message for normal handling

---

### 3.4 peers/spectator.py

Spectator-specific implementation.

### Constructor

```python
class Spectator(BasePeer):
    def __init__(self):
        super().__init__(
            pokemon=None,
            db=None,
            comm_mode="P2P",
            is_host=False
        )
        self.connected = False
```

**Key point:**

- `pokemon=None` and `db=None` because spectators don't battle

### Method: `process_message()` (override)

```python
def process_message(self, message: dict, sender_address: tuple):
    message_type = message.get("message_type")

    if message_type == MessageType.HANDSHAKE_RESPONSE:
        self.connected = True
        return

    if message_type == MessageType.CHAT_MESSAGE:
        self._display_chat_message(message)
        return

    if message_type == MessageType.BATTLE_SETUP:
        pokemon_name = message.get("pokemon_name", "Unknown")
        print(f"[SETUP] A player has selected {pokemon_name}!")
        return

    if message_type == MessageType.ATTACK_ANNOUNCE:
        move_name = message.get("move_name", "Unknown")
        print(f"[ATTACK] Move used: {move_name}")
        return

    if message_type == MessageType.CALCULATION_REPORT:
        self._display_damage_report(message)
        return

    if message_type == MessageType.GAME_OVER:
        self._display_game_over(message)
        return
```

**Key points:**

- Doesn't call parent's `process_message`
- Only displays messages (no battle logic)
- Different handlers for different message types

### Method: `chat()` (override)

```python
def chat(self):
    try:
        user_input = input()
    except EOFError:
        return

    if not user_input.strip():
        return

    chat_message = MessageFactory.chat_text(self.name, user_input)
    self.reliability.send_with_ack(chat_message, self.remote_addr)
```

**How it works:**

- Simpler than base chat (no commands)
- Any input becomes a chat message
- Spectators can only chat

---

## Summary

This completes the detailed code documentation for the PokeProtocol codebase. Each file, class, and function has been explained with:

- What it does
- How it works internally
- Key patterns and concepts used
- Step-by-step breakdowns of complex logic

The codebase follows a clean architecture:

- **Entry point** (`main.py`) handles user interaction
- **Protocol layer** handles message format, reliability, and game logic
- **Peer layer** handles network communication and role-specific behavior

Key patterns used throughout:

- **Factory pattern** (MessageFactory)
- **Inheritance** (BasePeer → Host/Joiner/Spectator)
- **Threading** (listener loops, background sending)
- **Queue-based communication** (ACK queue)
- **State machine** (BattlePhase enum)
