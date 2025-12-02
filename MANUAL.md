# PokeProtocol - Complete Manual

This manual explains everything you need to know about the PokeProtocol codebase, from basic concepts to detailed implementation.

---

## Table of Contents

1. [What is PokeProtocol?](#1-what-is-pokeprotocol)
2. [Prerequisites](#2-prerequisites)
3. [Quick Start Guide](#3-quick-start-guide)
4. [Understanding the Basics](#4-understanding-the-basics)
5. [How the Protocol Works](#5-how-the-protocol-works)
6. [Step-by-Step Flow](#6-step-by-step-flow)
7. [Codebase Structure](#7-codebase-structure)
8. [Detailed File Explanations](#8-detailed-file-explanations)
9. [Message Types Reference](#9-message-types-reference)
10. [Battle Mechanics](#10-battle-mechanics)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. What is PokeProtocol?

PokeProtocol is a **peer-to-peer Pokemon battle game** that runs over a computer network. It allows two players to:

- Connect over the internet or a local network
- Choose their Pokemon from a database of 801 Pokemon
- Battle each other in a turn-based combat system
- Send chat messages and stickers during battle

### Key Features

- **Peer-to-Peer Architecture**: No central server needed
- **UDP Communication**: Fast, lightweight network protocol
- **Reliable Messaging**: Guaranteed delivery with acknowledgments
- **Synchronized Battles**: Both players see the same results
- **Spectator Support**: Others can watch battles live

### The Three Roles

| Role          | Description                                                       |
| ------------- | ----------------------------------------------------------------- |
| **Host**      | Creates a new game and waits for players. Goes first in battle.   |
| **Joiner**    | Connects to an existing game. Goes second in battle.              |
| **Spectator** | Watches the battle without participating. Can send chat messages. |

---

## 2. Prerequisites

### Software Requirements

- **Python 3.7+** (tested with Python 3.8-3.11)
- No additional packages required (uses only Python standard library)

### Knowledge Requirements

To understand this codebase, it helps to know:

1. **Basic Python**: Variables, functions, classes, imports
2. **Basic Networking** (we explain this below)
3. **Basic OOP**: Inheritance, methods, objects

### Network Concepts Explained

#### What is a Socket?

A socket is like a phone line for your program. It lets you send and receive data over a network. You create a socket, tell it where to connect, and then send/receive messages.

#### What is UDP?

UDP (User Datagram Protocol) is one way to send data over a network. Think of it like sending a postcard:

- **Fast**: You just drop it in the mailbox
- **Simple**: No complicated setup
- **Unreliable**: It might get lost (but we fix this!)

#### What is an IP Address?

An IP address identifies a computer on a network, like `192.168.1.100`. Special addresses:

- `127.0.0.1` = Your own computer (localhost)
- `255.255.255.255` = Everyone on local network (broadcast)

#### What is a Port?

A port is like an apartment number. The IP gets you to the building (computer), the port gets you to the apartment (program). We use ports above 5000 to avoid conflicts.

---

## 3. Quick Start Guide

### Running Your First Battle

#### Step 1: Start the Host (Player 1)

```bash
python main.py
```

1. Enter `h` for Host
2. Choose communication mode: `1` for P2P
3. Enter your Pokemon ID (e.g., `25` for Pikachu)
4. Enter your IP address (e.g., `192.168.1.100`)
5. Enter a port number (e.g., `5001`)
6. Wait for a Joiner to connect...
7. Enter `Y` to accept the connection
8. Enter a random seed (any number, e.g., `12345`)

#### Step 2: Start the Joiner (Player 2)

```bash
python main.py
```

1. Enter `j` for Joiner
2. Choose communication mode: `1` for P2P
3. Enter your Pokemon ID (e.g., `4` for Charmander)
4. Enter the Host's IP address
5. Enter the Host's port number

#### Step 3: Battle!

Once connected, use these commands:

| Command    | Description                                      |
| ---------- | ------------------------------------------------ |
| `!attack`  | Attack the opponent                              |
| `!defend`  | Arm a defense boost for the next incoming attack |
| `!chat`    | Send a text message                              |
| `!sticker` | Send a sticker (image data)                      |

The Host attacks first, then turns alternate until one Pokemon faints!

---

## 4. Understanding the Basics

### How Messages Work

All communication uses text messages in this format:

```
key1: value1
key2: value2
key3: value3
```

Example of an ATTACK_ANNOUNCE message:

```
message_type: ATTACK_ANNOUNCE
move_name: Thunderbolt
sequence_number: 5
```

### How Reliability Works

Since UDP can lose messages, we add reliability:

1. **Sequence Numbers**: Every message gets a number (1, 2, 3...)
2. **ACKs (Acknowledgments)**: Receiver sends back "I got message #5"
3. **Retries**: If no ACK in 500ms, try again (up to 3 times)

```
Sender                          Receiver
   |                               |
   |--- Message (seq=5) ---------> |
   |                               |
   | <-------- ACK (ack=5) ------- |
   |                               |
   |   "Message delivered!"        |
```

### How Synchronized Random Numbers Work

Both players calculate damage independently. To get the same "random" results:

1. Host picks a random seed (any number)
2. Host sends seed to Joiner in HANDSHAKE_RESPONSE
3. Both initialize their random generator with the same seed
4. Now both get identical "random" numbers!

---

## 5. How the Protocol Works

### The Four Phases

```
┌─────────────────────────────────────────────────────────────┐
│                    PROTOCOL PHASES                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   1. CONNECTION     2. SETUP      3. BATTLE    4. END      │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐  ┌─────────┐  │
│   │Handshake │ → │  Battle  │ → │  Attack  │→ │ Game    │  │
│   │          │   │  Setup   │   │  Turns   │  │ Over    │  │
│   └──────────┘   └──────────┘   └──────────┘  └─────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Phase 1: Connection (Handshake)

```
JOINER                                    HOST
   │                                        │
   │ 1. "Can I join your game?"             │
   │ ────── HANDSHAKE_REQUEST ───────────► │
   │                                        │
   │                                        │ (User accepts)
   │                                        │
   │         2. "Yes! Here's our seed"      │
   │ ◄────── HANDSHAKE_RESPONSE ─────────  │
   │              (seed: 12345)             │
   │                                        │
```

### Phase 2: Battle Setup

```
JOINER                                    HOST
   │                                        │
   │ 3. "I'm using Pikachu"                │
   │ ────── BATTLE_SETUP ─────────────────►│
   │                                        │
   │         4. "I'm using Charmander"      │
   │ ◄────── BATTLE_SETUP ─────────────────│
   │                                        │
   │      BATTLE READY! Host goes first.   │
```

### Phase 3: Battle (Attack Turns)

Each attack follows a **4-step handshake**:

```
ATTACKER                                  DEFENDER
   │                                        │
   │ Step 1: "I'm using Thunderbolt!"      │
   │ ────── ATTACK_ANNOUNCE ──────────────►│
   │                                        │
   │         Step 2: "I'm ready to defend"  │
   │ ◄────── DEFENSE_ANNOUNCE ─────────────│
   │                                        │
   │ Step 3: "I calculated 50 damage"       │
   │ ────── CALCULATION_REPORT ───────────►│
   │ ◄────── CALCULATION_REPORT ───────────│
   │         "I also calculated 50 damage"  │
   │                                        │
   │ Step 4a: "We agree! Apply damage"      │
   │ ────── CALCULATION_CONFIRM ──────────►│
   │                                        │
   │            (Turn switches)             │
```

If calculations don't match (rare), Step 4 sends RESOLUTION_REQUEST instead.

### Phase 4: Game Over

When a Pokemon's HP reaches 0:

```
ATTACKER                                  DEFENDER
   │                                        │
   │ "Charmander fainted! Pikachu wins!"   │
   │ ────── GAME_OVER ────────────────────►│
   │                                        │
   │              BATTLE ENDED              │
```

---

## 6. Step-by-Step Flow

### Complete Flow Walkthrough

Let's trace exactly what happens when two players battle:

#### 1. Programs Start

**Host runs `main.py`:**

```
1. main.py loads Pokemon database (801 Pokemon)
2. User chooses 'h' for Host
3. User selects Pokemon (e.g., ID 25 = Pikachu)
4. Host object is created:
   - Socket created (UDP, allows broadcast)
   - BattleManager created (tracks turns, damage)
   - ReliableChannel created (handles ACKs)
5. Socket bound to IP:port (e.g., 192.168.1.100:5001)
6. Accept loop starts in background thread
7. Host waits for HANDSHAKE_REQUEST...
```

**Joiner runs `main.py`:**

```
1. main.py loads Pokemon database
2. User chooses 'j' for Joiner
3. User selects Pokemon (e.g., ID 4 = Charmander)
4. User enters Host's IP and port
5. Joiner object is created
6. Listener loop starts in background thread
7. Joiner sends HANDSHAKE_REQUEST to Host
```

#### 2. Connection Established

```
Host receives HANDSHAKE_REQUEST:
  └─► Puts request in queue
  └─► Asks user "Accept? (Y/N)"
  └─► User enters Y
  └─► User enters seed (e.g., 12345)
  └─► Sends HANDSHAKE_RESPONSE with seed
  └─► Initializes RNG with seed 12345

Joiner receives HANDSHAKE_RESPONSE:
  └─► Extracts seed (12345)
  └─► Initializes RNG with seed 12345
  └─► Now both have synchronized RNG!
```

#### 3. Battle Setup Exchange

```
Joiner sends BATTLE_SETUP:
  └─► message_type: BATTLE_SETUP
  └─► pokemon_name: Charmander
  └─► stat_boosts: {special_attack_uses: 5, special_defense_uses: 5}

Host receives BATTLE_SETUP:
  └─► handle_battle_setup() called
  └─► Looks up "charmander" in database
  └─► Stores as opp_mon (opponent's Pokemon)
  └─► Parses stat_boosts
  └─► _on_battle_setup() sends Host's BATTLE_SETUP

Joiner receives Host's BATTLE_SETUP:
  └─► Stores Host's Pokemon as opp_mon
  └─► Battle is now ready!
  └─► BattlePhase = WAITING_FOR_MOVE
  └─► Host's is_my_turn = True
  └─► Joiner's is_my_turn = False
```

#### 4. First Attack (Host Attacks)

**Host types `!attack`:**

```python
# In base_peer.py perform_attack():
1. Check: is_my_turn == True? ✓
2. Check: battle_phase == WAITING_FOR_MOVE? ✓
3. Display Pokemon's moves
4. User picks "Thunderbolt"
5. Ask about special attack boost
6. Create ATTACK_ANNOUNCE message:
   {"message_type": "ATTACK_ANNOUNCE", "move_name": "Thunderbolt"}
7. Send with reliability layer
```

**Joiner receives ATTACK_ANNOUNCE:**

```python
# In message_handlers.py handle_attack_announce():
1. Parse move_name: "Thunderbolt"
2. Store pending attack info:
   - pending_attacker = opp_mon (Host's Pokemon)
   - pending_defender = pokemon (Joiner's Pokemon)
   - pending_move = Move("Thunderbolt", ...)
3. Check for armed defense boost
4. Calculate damage:
   - Get attacker's Special Attack stat
   - Get defender's Special Defense stat
   - Apply type multiplier (Electric vs Fire = 1.0)
   - damage = (attack * multiplier) / defense
5. Store calculation for comparison
6. Create DEFENSE_ANNOUNCE and CALCULATION_REPORT
7. Send both to Host
```

**Host receives DEFENSE_ANNOUNCE:**

```python
# In message_handlers.py handle_defense_announce():
1. Confirm opponent acknowledged attack
2. Calculate damage with own stats
3. Apply attack boost multiplier if used
4. Store calculation
5. Send CALCULATION_REPORT to Joiner
```

**Both receive CALCULATION_REPORT:**

```python
# In message_handlers.py handle_calculation_report():
1. Parse opponent's damage calculation
2. Compare with our calculation:
   - Our damage: 50
   - Their damage: 50
3. If equal:
   - Send CALCULATION_CONFIRM
   - Apply damage to defender
   - Check if defender fainted (HP <= 0)
   - Switch turns
4. If not equal:
   - Send RESOLUTION_REQUEST
```

**Host receives CALCULATION_CONFIRM:**

```python
# In message_handlers.py handle_calculation_confirm():
1. Apply confirmed damage to opponent
2. Check for game over
3. switch_turn():
   - is_my_turn = False (now Joiner's turn)
   - battle_phase = WAITING_FOR_MOVE
   - Reset pending_move, pending_attacker, etc.
4. Print "Waiting for opponent's move..."
```

#### 5. Second Attack (Joiner Attacks)

Now it's Joiner's turn. The same process repeats:

- Joiner sends ATTACK_ANNOUNCE
- Host sends DEFENSE_ANNOUNCE + CALCULATION_REPORT
- Both compare calculations
- Damage applied, turns switch again

#### 6. Battle Ends

```python
# When defender's HP <= 0:
1. In handle_calculation_report():
   - defender.current_hp = 0
   - create_game_over_message()
   - winner = attacker.name
   - loser = defender.name
2. Send CALCULATION_CONFIRM + GAME_OVER
3. Set running = False, listening = False
4. Close socket

# Other peer receives GAME_OVER:
1. In handle_game_over():
   - Print winner and loser
2. Set running = False, listening = False
3. Close socket
```

---

## 7. Codebase Structure

```
PokeProtocol/
│
├── main.py                      # Entry point - run this to start
│
├── peers/                       # Peer implementations
│   ├── __init__.py
│   ├── base_peer.py            # Common code for all peers
│   ├── host.py                 # Host-specific code
│   ├── joiner.py               # Joiner-specific code
│   └── spectator.py            # Spectator-specific code
│
├── protocol/                    # Protocol implementation
│   ├── __init__.py
│   ├── constants.py            # Message types, constants
│   ├── messages.py             # Encode/decode text format
│   ├── message_factory.py      # Create messages correctly
│   ├── reliability.py          # ACKs and retries
│   ├── message_handlers.py     # Process each message type
│   ├── battle_state.py         # Pokemon, moves, damage calc
│   ├── battle_manager.py       # Turn management, game state
│   └── pokemon_db.py           # Load Pokemon database
│
├── pokemon_data.json           # Pokemon database (801 Pokemon)
│
├── test_protocol.py            # Unit tests
├── test_e2e_protocol.py        # End-to-end tests
├── test_message_factory.py     # Message factory tests
│
├── ARCHITECTURE.md             # Architecture overview
└── MANUAL.md                   # This file
```

---

## 8. Detailed File Explanations

### Entry Point

#### `main.py`

**Purpose:** Starting point for the application.

**What it does:**

1. Shows menu (Host/Joiner/Spectator)
2. Gets user settings (Pokemon, IP, port)
3. Creates the appropriate peer object
4. Starts the peer

**Key functions:**

- `main()` - Entry point
- `get_communication_mode()` - P2P or Broadcast
- `get_pokemon_id()` - Choose Pokemon
- `run_host()`, `run_joiner()`, `run_spectator()` - Start each role

---

### Peer Layer

#### `peers/base_peer.py`

**Purpose:** Common functionality shared by Host, Joiner, and Spectator.

**What it does:**

1. Sets up the UDP socket
2. Runs the listener loop (background thread)
3. Handles ACKs and sequence numbers
4. Routes messages to the right handler
5. Provides attack and chat functionality

**Key components:**

```python
class BasePeer:
    # Core attributes
    self.pokemon          # Our Pokemon
    self.opp_mon          # Opponent's Pokemon
    self.sock             # UDP socket
    self.battle_manager   # Turn/damage management
    self.reliability      # Reliable message sending

    # Key methods
    def listen_loop()          # Background thread for receiving
    def process_message()      # Route to correct handler
    def perform_attack()       # Execute an attack
    def chat()                 # User command interface
```

#### `peers/host.py`

**Purpose:** Host-specific functionality.

**What it does:**

1. Binds to IP:port and waits
2. Accepts/rejects connection requests
3. Sends the random seed
4. Forwards messages to spectators

**Key additions to BasePeer:**

- `accept()` - Main accept loop
- `_accept_loop()` - Listen for HANDSHAKE_REQUEST
- `_on_battle_setup()` - Send own BATTLE_SETUP
- Spectator support

#### `peers/joiner.py`

**Purpose:** Joiner-specific functionality.

**What it does:**

1. Connects to Host
2. Receives and processes seed
3. Sends BATTLE_SETUP first

**Key additions to BasePeer:**

- `start()` - Connect to host
- `_send_handshake()` - Send HANDSHAKE_REQUEST
- `_send_battle_setup()` - Send own Pokemon info

#### `peers/spectator.py`

**Purpose:** Watch battles without participating.

**What it does:**

1. Connects as spectator
2. Displays battle messages nicely
3. Can only send chat messages

**Key differences:**

- No Pokemon
- No attack capability
- Display-only message handling

---

### Protocol Layer

#### `protocol/constants.py`

**Purpose:** Define all constant values used in the protocol.

**Contents:**

```python
class MessageType:
    HANDSHAKE_REQUEST = "HANDSHAKE_REQUEST"
    HANDSHAKE_RESPONSE = "HANDSHAKE_RESPONSE"
    BATTLE_SETUP = "BATTLE_SETUP"
    ATTACK_ANNOUNCE = "ATTACK_ANNOUNCE"
    DEFENSE_ANNOUNCE = "DEFENSE_ANNOUNCE"
    CALCULATION_REPORT = "CALCULATION_REPORT"
    CALCULATION_CONFIRM = "CALCULATION_CONFIRM"
    RESOLUTION_REQUEST = "RESOLUTION_REQUEST"
    GAME_OVER = "GAME_OVER"
    CHAT_MESSAGE = "CHAT_MESSAGE"
    ACK = "ACK"

# Timing
ACK_TIMEOUT_SECONDS = 0.5
MAX_RETRIES = 3

# Battle
DEFAULT_SPECIAL_ATTACK_USES = 5
DEFAULT_SPECIAL_DEFENSE_USES = 5
BOOST_MULTIPLIER = 1.5
```

#### `protocol/messages.py`

**Purpose:** Convert between Python dictionaries and text strings.

**Functions:**

```python
def encode_message(dict) -> str:
    # {"type": "ATTACK", "move": "Tackle"}
    # becomes:
    # "type: ATTACK\nmove: Tackle"

def decode_message(str) -> dict:
    # Reverse of encode_message
```

#### `protocol/message_factory.py`

**Purpose:** Create correctly-formatted messages.

**Why use this?**
Instead of manually creating dictionaries (error-prone):

```python
msg = {"message_type": "ATTACK_ANOUNCE", "move": "Tackle"}  # Typo!
```

Use the factory (safe):

```python
msg = MessageFactory.attack_announce("Tackle")  # Always correct
```

**Available functions:**

- `handshake_request()`
- `handshake_response(seed)`
- `battle_setup(comm_mode, pokemon_name)`
- `attack_announce(move_name)`
- `defense_announce()`
- `calculation_report(...)`
- `calculation_confirm()`
- `resolution_request(...)`
- `game_over(winner, loser)`
- `chat_text(sender, text)`
- `chat_sticker(sender, data)`
- `ack(ack_number)`

#### `protocol/reliability.py`

**Purpose:** Make UDP reliable with ACKs and retries.

**How it works:**

```
1. Add sequence_number to message
2. Send message
3. Start timer (500ms)
4. Wait for ACK with matching ack_number
5. If ACK received: Success! Increment sequence.
6. If timeout: Retry (up to 3 times)
7. If all retries fail: Return False
```

**Key class:**

```python
class ReliableChannel:
    def send_with_ack(message, address) -> bool:
        # Returns True if delivered, False if failed
```

#### `protocol/message_handlers.py`

**Purpose:** Process each type of incoming message.

**Functions:**

```python
handle_battle_setup()        # Store opponent's Pokemon
handle_attack_announce()     # Respond to incoming attack
handle_defense_announce()    # Calculate and send report
handle_calculation_report()  # Compare calculations
handle_calculation_confirm() # Apply damage, switch turns
handle_resolution_request()  # Handle calculation mismatch
handle_game_over()           # End the battle
```

Each handler:

1. Parses the message
2. Updates game state
3. Creates response message(s)
4. Returns messages to send

#### `protocol/battle_state.py`

**Purpose:** Pokemon game mechanics.

**Classes:**

```python
class Pokemon:
    name, max_hp, current_hp
    attack, special_attack
    physical_defense, special_defense
    type1, type2, type_multipliers
    moves

class Move:
    name, base_power, category, move_type

class BattleState:
    attacker, defender
```

**Key functions:**

```python
def calculate_damage(state, move, attack_boost, defense_boost):
    # Formula: (attack * type_multiplier) / defense

def generate_status_message(attacker, move, multiplier):
    # "Pikachu used Thunderbolt! It was super effective!"
```

**Type effectiveness:**

- multiplier > 1.0 = "Super effective!" (2x damage)
- multiplier < 1.0 = "Not very effective..." (0.5x damage)
- multiplier = 0.0 = "No effect..." (0 damage)

#### `protocol/battle_manager.py`

**Purpose:** Manage battle flow and state.

**Key attributes:**

```python
class BattleManager:
    is_host              # Are we the host?
    is_my_turn           # Is it our turn?
    battle_phase         # WAITING_FOR_MOVE or PROCESSING_TURN

    pending_move         # Current move being processed
    pending_attacker     # Who is attacking
    pending_defender     # Who is defending
    my_calculation       # Our damage calculation

    # Stat boosts
    special_attack_uses  # Remaining attack boosts (starts at 5)
    special_defense_uses # Remaining defense boosts (starts at 5)
```

**Key methods:**

```python
def can_attack()              # Check if we can attack now
def prepare_attack()          # Set up attack, create message
def switch_turn()             # Change whose turn it is
def use_special_attack()      # Use an attack boost
def arm_defense_boost()       # Prepare defense for next attack
def create_calculation_report()  # Build report message
```

#### `protocol/pokemon_db.py`

**Purpose:** Load Pokemon from the database file.

**Function:**

```python
def load_pokemon_db() -> dict:
    # Reads pokemon_data.json
    # Returns {id: Pokemon, ...}
    # Also indexed by lowercase name
```

---

## 9. Message Types Reference

### HANDSHAKE_REQUEST

**Sent by:** Joiner → Host
**Purpose:** Request to join a game
**Fields:**

```
message_type: HANDSHAKE_REQUEST
```

### HANDSHAKE_RESPONSE

**Sent by:** Host → Joiner
**Purpose:** Accept connection, share seed
**Fields:**

```
message_type: HANDSHAKE_RESPONSE
seed: 12345
```

### BATTLE_SETUP

**Sent by:** Both peers
**Purpose:** Share Pokemon information
**Fields:**

```
message_type: BATTLE_SETUP
communication_mode: P2P
pokemon_name: Pikachu
stat_boosts: {'special_attack_uses': 5, 'special_defense_uses': 5}
```

### ATTACK_ANNOUNCE

**Sent by:** Attacker → Defender
**Purpose:** Announce attack
**Fields:**

```
message_type: ATTACK_ANNOUNCE
move_name: Thunderbolt
sequence_number: 5
```

### DEFENSE_ANNOUNCE

**Sent by:** Defender → Attacker
**Purpose:** Acknowledge attack received
**Fields:**

```
message_type: DEFENSE_ANNOUNCE
sequence_number: 6
```

### CALCULATION_REPORT

**Sent by:** Both peers
**Purpose:** Share damage calculation
**Fields:**

```
message_type: CALCULATION_REPORT
attacker: Pikachu
move_used: Thunderbolt
remaining_health: 100
damage_dealt: 50
defender_hp_remaining: 45
status_message: Pikachu used Thunderbolt!
sequence_number: 7
```

### CALCULATION_CONFIRM

**Sent by:** One peer
**Purpose:** Confirm calculations match
**Fields:**

```
message_type: CALCULATION_CONFIRM
sequence_number: 8
```

### RESOLUTION_REQUEST

**Sent by:** One peer (when calculations differ)
**Purpose:** Resolve calculation mismatch
**Fields:**

```
message_type: RESOLUTION_REQUEST
attacker: Pikachu
move_used: Thunderbolt
damage_dealt: 48
defender_hp_remaining: 47
sequence_number: 9
```

### GAME_OVER

**Sent by:** Attacker when defender faints
**Purpose:** End the battle
**Fields:**

```
message_type: GAME_OVER
winner: Pikachu
loser: Charmander
sequence_number: 10
```

### CHAT_MESSAGE

**Sent by:** Any peer
**Purpose:** Send text or sticker
**Fields (text):**

```
message_type: CHAT_MESSAGE
sender_name: Player1
content_type: TEXT
message_text: Good luck!
sequence_number: 11
```

**Fields (sticker):**

```
message_type: CHAT_MESSAGE
sender_name: Player1
content_type: STICKER
sticker_data: <base64 data>
sequence_number: 12
```

### ACK

**Sent by:** Receiver of any message
**Purpose:** Confirm receipt
**Fields:**

```
message_type: ACK
ack_number: 5
```

---

## 10. Battle Mechanics

### Damage Formula

```
Damage = (Attacker's Stat × Type Multiplier) / Defender's Stat
```

Where:

- **Attacker's Stat**: Attack (physical moves) or Special Attack (special moves)
- **Type Multiplier**: Based on move type vs defender's type
- **Defender's Stat**: Defense (physical) or Special Defense (special)

### Physical vs Special Moves

**Physical types** (use Attack/Defense):

- Normal, Fighting, Flying, Poison, Ground, Rock, Bug, Ghost, Steel

**Special types** (use Sp. Attack/Sp. Defense):

- Fire, Water, Grass, Electric, Psychic, Ice, Dragon, Dark, Fairy

### Type Effectiveness

| Multiplier | Meaning            | Example            |
| ---------- | ------------------ | ------------------ |
| 2.0x       | Super effective    | Electric vs Water  |
| 1.0x       | Normal             | Normal vs Normal   |
| 0.5x       | Not very effective | Fire vs Water      |
| 0.0x       | No effect          | Electric vs Ground |

### Stat Boosts

Each player starts with:

- **5 Special Attack boosts**: Multiply attack by 1.5x
- **5 Special Defense boosts**: Multiply defense by 1.5x

**Using Attack Boost:**

1. When you choose to attack, you're asked if you want to use a boost
2. If yes, your attack stat is multiplied by 1.5 for that turn
3. One use is consumed (can't be undone)

**Using Defense Boost:**

1. When waiting for opponent's attack, type `!defend`
2. The boost is "armed" for the next incoming attack
3. When attacked, your defense is multiplied by 1.5
4. One use is consumed

### Turn Order

1. Host always goes first
2. After each successful attack, turns switch
3. Battle continues until one Pokemon's HP reaches 0

---

## 11. Troubleshooting

### Common Issues

#### "Connection refused" or timeout connecting

**Causes:**

- Host not running yet
- Wrong IP address or port
- Firewall blocking UDP

**Solutions:**

1. Start Host first, then Joiner
2. Verify IP address: Host should tell Joiner their IP
3. Try disabling firewall temporarily
4. Make sure both are on same network for broadcast mode

#### "No ACK received" messages

**Causes:**

- Network issues
- Other peer disconnected
- Firewall blocking responses

**Solutions:**

1. Check network connection
2. Restart both programs
3. Try using different port (above 5000)

#### Different damage calculations

**Causes:**

- Bug in code (should be fixed)
- Network caused state desync

**Solutions:**

1. The protocol handles this with RESOLUTION_REQUEST
2. One peer's calculation is accepted
3. If persistent, restart both programs

#### "Unknown Pokemon" error

**Causes:**

- Pokemon name not in database
- Typo in Pokemon name

**Solutions:**

1. Use Pokedex ID (1-801) instead of name
2. Check pokemon_data.json exists

### Running Tests

To verify everything works:

```bash
# Unit tests
python test_protocol.py

# End-to-end tests
python test_e2e_protocol.py

# Message factory tests
python test_message_factory.py
```

All tests should show "ALL TESTS PASSED!"

### Debug Tips

1. **Print statements**: The code prints most important events
2. **Message logging**: All received messages are printed
3. **ACK tracking**: You can see when ACKs are sent/received

### Getting Help

If you're stuck:

1. Check this manual for the relevant section
2. Read the comments in the source code
3. Look at test files for usage examples
4. Trace through the step-by-step flow above

---

## Appendix: Quick Reference

### Command Cheat Sheet

| Command    | When to Use     | Effect                            |
| ---------- | --------------- | --------------------------------- |
| `!attack`  | Your turn       | Choose and execute a move         |
| `!defend`  | Opponent's turn | Arm defense boost for next attack |
| `!chat`    | Anytime         | Send a text message               |
| `!sticker` | Anytime         | Send a sticker                    |

### Important Files

| File                  | What to Read It For           |
| --------------------- | ----------------------------- |
| `main.py`             | How the program starts        |
| `base_peer.py`        | How messages are processed    |
| `message_handlers.py` | What happens for each message |
| `battle_state.py`     | How damage is calculated      |
| `reliability.py`      | How messages are guaranteed   |

### Message Flow Summary

```
CONNECT:    HANDSHAKE_REQUEST → HANDSHAKE_RESPONSE
SETUP:      BATTLE_SETUP ↔ BATTLE_SETUP
ATTACK:     ATTACK_ANNOUNCE → DEFENSE_ANNOUNCE →
            CALCULATION_REPORT ↔ CALCULATION_REPORT →
            CALCULATION_CONFIRM (or RESOLUTION_REQUEST)
END:        GAME_OVER
```

---

_This manual was generated for the PokeProtocol codebase. For architecture diagrams and code structure, see ARCHITECTURE.md._
