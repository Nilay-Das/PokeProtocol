# PokeProtocol Architecture Guide

This document explains how the PokeProtocol codebase is organized and how the different pieces work together.

## Overview

PokeProtocol is a peer-to-peer Pokemon battle game that runs over UDP. Two players connect, choose their Pokemon, and battle!

```
┌─────────────────────────────────────────────────────────────┐
│                        PokeProtocol                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐          ┌─────────┐          ┌─────────────┐ │
│  │  HOST   │◄────────►│ JOINER  │          │  SPECTATOR  │ │
│  │(Server) │  Battle  │(Client) │          │  (Viewer)   │ │
│  └─────────┘          └─────────┘          └─────────────┘ │
│       │                    │                      ▲        │
│       │    UDP Messages    │                      │        │
│       └────────────────────┴──────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
PokeProtocol/
├── main.py                    # Entry point - starts the application
├── ARCHITECTURE.md            # This file
│
├── peers/                     # Peer implementations
│   ├── __init__.py
│   ├── base_peer.py          # Common code for Host/Joiner
│   ├── host.py               # Host (server) implementation
│   ├── joiner.py             # Joiner (client) implementation
│   └── spectator.py          # Spectator (viewer) implementation
│
├── protocol/                  # Protocol implementation
│   ├── __init__.py
│   ├── constants.py          # Message types and constants
│   ├── messages.py           # Encode/decode messages
│   ├── message_factory.py    # Create protocol messages
│   ├── reliability.py        # ACKs and retries over UDP
│   ├── message_handlers.py   # Process incoming messages
│   ├── battle_state.py       # Pokemon, moves, damage calculation
│   ├── battle_manager.py     # Turn management, game state
│   └── pokemon_db.py         # Load Pokemon database
│
└── tests/                     # Test files
    ├── test_protocol.py      # Unit tests
    └── test_e2e_protocol.py  # End-to-end tests
```

## How the Pieces Fit Together

### 1. Main Entry Point (`main.py`)

The user runs `main.py` and chooses their role:
- Host: Creates a new game
- Joiner: Joins an existing game
- Spectator: Watches a game

### 2. Peer Classes (`peers/`)

All peers inherit from `BasePeer`:

```
                ┌──────────────┐
                │   BasePeer   │
                │    (base)    │
                └──────────────┘
                       ▲
           ┌──────────┼──────────┐
           │          │          │
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │   Host   │ │  Joiner  │ │ Spectator│
    └──────────┘ └──────────┘ └──────────┘
```

**BasePeer** provides:
- Socket setup
- Listener loop (runs in background thread)
- Message processing
- Chat functionality
- Attack functionality

**Host** adds:
- Accept connections
- Set random seed
- Support spectators

**Joiner** adds:
- Connect to host
- Receive random seed

**Spectator** adds:
- Display-only message handling

### 3. Protocol Layer (`protocol/`)

```
┌──────────────────────────────────────────────────────────────┐
│                     PROTOCOL LAYER                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │ message_factory │───►│    messages     │                 │
│  │  (create msgs)  │    │ (encode/decode) │                 │
│  └─────────────────┘    └────────┬────────┘                 │
│                                  │                          │
│                                  ▼                          │
│                         ┌─────────────────┐                 │
│                         │   reliability   │                 │
│                         │ (ACKs, retries) │                 │
│                         └────────┬────────┘                 │
│                                  │                          │
│                                  ▼                          │
│                         ┌─────────────────┐                 │
│                         │     SOCKET      │                 │
│                         │    (UDP/IP)     │                 │
│                         └─────────────────┘                 │
└──────────────────────────────────────────────────────────────┘
```

## Message Flow

### Connection Handshake

```
JOINER                                 HOST
   │                                    │
   │────── HANDSHAKE_REQUEST ─────────►│
   │                                    │
   │◄───── HANDSHAKE_RESPONSE ────────│
   │         (with seed)               │
   │                                    │
```

### Battle Setup

```
JOINER                                 HOST
   │                                    │
   │────── BATTLE_SETUP ──────────────►│
   │       (Pokemon info)              │
   │                                    │
   │◄───── BATTLE_SETUP ──────────────│
   │       (Pokemon info)              │
   │                                    │
```

### Attack Flow (4-Step Handshake)

```
ATTACKER                              DEFENDER
   │                                    │
   │──(1)── ATTACK_ANNOUNCE ──────────►│
   │                                    │
   │◄─(2)── DEFENSE_ANNOUNCE ─────────│
   │                                    │
   │──(3)── CALCULATION_REPORT ───────►│
   │◄─(3)── CALCULATION_REPORT ───────│
   │                                    │
   │──(4)── CALCULATION_CONFIRM ──────►│
   │        (or RESOLUTION_REQUEST)    │
   │                                    │
```

## Key Concepts

### UDP and Reliability

UDP doesn't guarantee message delivery, so we add our own reliability:

1. **Sequence Numbers**: Every message has a number (1, 2, 3...)
2. **ACKs**: Receiver sends back an ACK with the sequence number
3. **Retries**: If no ACK received in 500ms, retry up to 3 times

### Synchronized Random Numbers

Both peers need to calculate the same damage. We use a seeded RNG:

1. Host picks a random seed (any integer)
2. Host sends seed in HANDSHAKE_RESPONSE
3. Both peers initialize their RNG with that seed
4. Now both RNGs produce the same "random" numbers!

### Turn-Based Battle

```
┌─────────────────────────────────────────┐
│           BATTLE STATE MACHINE          │
├─────────────────────────────────────────┤
│                                         │
│   ┌─────────────────────────────────┐  │
│   │       WAITING_FOR_MOVE          │  │
│   │  (Someone needs to attack)      │  │
│   └───────────────┬─────────────────┘  │
│                   │                     │
│           ATTACK_ANNOUNCE               │
│                   │                     │
│                   ▼                     │
│   ┌─────────────────────────────────┐  │
│   │       PROCESSING_TURN           │  │
│   │  (Calculating damage)           │  │
│   └───────────────┬─────────────────┘  │
│                   │                     │
│       CALCULATION_CONFIRM               │
│                   │                     │
│                   ▼                     │
│          (Switch turns)                 │
│                   │                     │
│                   └────► WAITING...     │
│                                         │
└─────────────────────────────────────────┘
```

## File-by-File Summary

| File | Purpose |
|------|---------|
| `main.py` | Entry point, user menu |
| `peers/base_peer.py` | Common peer functionality |
| `peers/host.py` | Host-specific logic |
| `peers/joiner.py` | Joiner-specific logic |
| `peers/spectator.py` | Spectator display logic |
| `protocol/constants.py` | Message types, constants |
| `protocol/messages.py` | Encode/decode text format |
| `protocol/message_factory.py` | Create messages correctly |
| `protocol/reliability.py` | ACKs and retries |
| `protocol/message_handlers.py` | Process each message type |
| `protocol/battle_state.py` | Pokemon, moves, damage |
| `protocol/battle_manager.py` | Turns, game state |
| `protocol/pokemon_db.py` | Load Pokemon data |

## How to Add New Features

### Adding a New Message Type

1. Add the constant to `protocol/constants.py`
2. Add a factory method in `protocol/message_factory.py`
3. Add a handler in `protocol/message_handlers.py`
4. Call the handler from `peers/base_peer.py` process_message()

### Adding a New Command

1. Add the command check in `peers/base_peer.py` chat() method
2. Create a helper method if needed
3. Send appropriate messages

### Adding a New Pokemon Stat

1. Add the attribute to the `Pokemon` class in `protocol/battle_state.py`
2. Update `protocol/pokemon_db.py` to load the new stat
3. Update damage calculation if needed

## Testing

Run the tests to verify everything works:

```bash
# Unit tests
python test_protocol.py

# End-to-end tests
python test_e2e_protocol.py

# Message factory tests
python test_message_factory.py
```

## Common Issues

### "Connection refused" error
- Make sure the Host is running before the Joiner connects
- Check that the IP address and port are correct

### "Timeout" errors
- Check network connectivity
- Make sure firewall isn't blocking UDP traffic

### Different damage calculations
- Verify both peers are using the same seed
- Check for floating point rounding issues

