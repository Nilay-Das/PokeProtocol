"""
=============================================================================
PROTOCOL CONSTANTS - All the "Magic Values" in One Place
=============================================================================

WHAT IS THIS FILE?
------------------
This file contains all the constant values used throughout the protocol.
Instead of writing "ATTACK_ANNOUNCE" in 10 different places, we define it
once here and use MessageType.ATTACK_ANNOUNCE everywhere else.

WHY USE CONSTANTS?
------------------
1. Avoid typos: If you type "ATACK_ANNOUNCE" by accident, Python won't
   catch the error. But MessageType.ATACK_ANNOUNCE will cause an error!

2. Easy to change: If we ever rename a message type, we only change it here.

3. Autocomplete: Your IDE can suggest MessageType.ATTACK_ANNOUNCE when you
   start typing MessageType.

4. Documentation: All the valid values are listed in one place.


HOW TO USE THIS FILE
--------------------
    from protocol.constants import MessageType, ContentType, CommunicationMode

    # Instead of writing:
    if message["message_type"] == "ATTACK_ANNOUNCE":
        ...

    # Write this (safer and clearer):
    if message["message_type"] == MessageType.ATTACK_ANNOUNCE:
        ...

=============================================================================
"""


class MessageType:
    """
    All the different types of messages in our protocol.
    
    Messages are categorized by their purpose in the battle flow.
    See ARCHITECTURE.md for the complete message flow diagram.
    """

    # =========================================================================
    # CONNECTION MESSAGES
    # These are used when peers first connect to each other
    # =========================================================================
    
    # Sent by joiner to host to request a connection
    # Flow: Joiner sends this, Host responds with HANDSHAKE_RESPONSE
    HANDSHAKE_REQUEST = "HANDSHAKE_REQUEST"
    
    # Sent by host to joiner to accept the connection and share the random seed
    # Contains: seed (int) - used to synchronize random number generation
    HANDSHAKE_RESPONSE = "HANDSHAKE_RESPONSE"
    
    # Sent by a spectator to request read-only access to the battle
    # Spectators can watch but not participate
    SPECTATOR_REQUEST = "SPECTATOR_REQUEST"

    # =========================================================================
    # BATTLE SETUP MESSAGES
    # These are used to exchange Pokemon information before the battle starts
    # =========================================================================
    
    # Sent by both peers to share their chosen Pokemon
    # Contains: communication_mode, pokemon_name, stat_boosts
    # Both peers send this after the handshake
    BATTLE_SETUP = "BATTLE_SETUP"

    # =========================================================================
    # TURN-BASED BATTLE MESSAGES (The 4-Step Handshake)
    # These messages handle each attack in the battle
    # 
    # Flow for each turn:
    #   1. Attacker sends ATTACK_ANNOUNCE
    #   2. Defender sends DEFENSE_ANNOUNCE
    #   3. Both send CALCULATION_REPORT
    #   4. One sends CALCULATION_CONFIRM (or RESOLUTION_REQUEST if they disagree)
    # =========================================================================
    
    # Step 1: Attacker announces they're using a move
    # Contains: move_name (the attack being used)
    ATTACK_ANNOUNCE = "ATTACK_ANNOUNCE"
    
    # Step 2: Defender acknowledges they received the attack announcement
    # Contains: nothing extra (just confirms receipt)
    DEFENSE_ANNOUNCE = "DEFENSE_ANNOUNCE"
    
    # Step 3: Both peers calculate damage and report their results
    # Contains: attacker, move_used, remaining_health, damage_dealt,
    #           defender_hp_remaining, status_message
    CALCULATION_REPORT = "CALCULATION_REPORT"
    
    # Step 4a: Confirms that damage calculations match
    # Contains: nothing extra (just confirms agreement)
    CALCULATION_CONFIRM = "CALCULATION_CONFIRM"

    # =========================================================================
    # DISCREPANCY RESOLUTION
    # Used when the two peers calculate different damage values
    # =========================================================================
    
    # Sent when damage calculations don't match
    # Contains: attacker, move_used, damage_dealt, defender_hp_remaining
    # The peers must agree on the correct values before continuing
    RESOLUTION_REQUEST = "RESOLUTION_REQUEST"

    # =========================================================================
    # GAME END MESSAGE
    # =========================================================================
    
    # Sent when one Pokemon faints (HP reaches 0)
    # Contains: winner, loser (Pokemon names)
    GAME_OVER = "GAME_OVER"

    # =========================================================================
    # CHAT MESSAGE
    # For communication between players outside of battle actions
    # =========================================================================
    
    # A text or sticker message between players
    # Contains: sender_name, content_type (TEXT or STICKER), 
    #           message_text OR sticker_data
    CHAT_MESSAGE = "CHAT_MESSAGE"

    # =========================================================================
    # RELIABILITY LAYER
    # Used by the ReliableChannel to confirm message delivery
    # =========================================================================
    
    # Acknowledgment that a message was received
    # Contains: ack_number (matches the sequence_number of the received message)
    ACK = "ACK"


class ContentType:
    """
    Types of content that can be sent in a CHAT_MESSAGE.
    
    Example usage:
        message = {
            "message_type": MessageType.CHAT_MESSAGE,
            "content_type": ContentType.TEXT,
            "message_text": "Good game!"
        }
    """
    
    # A regular text message
    TEXT = "TEXT"
    
    # A sticker (image data encoded as Base64 string)
    STICKER = "STICKER"


class CommunicationMode:
    """
    How peers communicate with each other.
    
    P2P (Peer-to-Peer):
        - Messages go directly from one peer to another
        - Requires knowing the other peer's IP address
        - More reliable, works over the internet
    
    BROADCAST:
        - Messages are sent to everyone on the local network
        - Uses special address 255.255.255.255
        - Only works on local network (same WiFi, same router)
        - Useful for finding peers without knowing their IP
    """
    
    # Direct communication between two specific peers
    P2P = "P2P"
    
    # Send to all devices on the local network
    BROADCAST = "BROADCAST"


# =============================================================================
# PROTOCOL TIMING CONSTANTS
# These values are specified in the RFC (protocol specification)
# =============================================================================

# How long to wait for an ACK before retrying (500 milliseconds)
ACK_TIMEOUT_SECONDS = 0.5

# Maximum number of retry attempts before giving up
MAX_RETRIES = 3


# =============================================================================
# BATTLE CONSTANTS
# =============================================================================

# Each player starts with 5 special attack boosts they can use
# Using a boost multiplies attack power by 1.5x for one turn
DEFAULT_SPECIAL_ATTACK_USES = 5

# Each player starts with 5 special defense boosts they can use
# Using a boost multiplies defense power by 1.5x for one turn
DEFAULT_SPECIAL_DEFENSE_USES = 5

# The multiplier applied when using a stat boost
# Example: 100 attack with boost = 100 * 1.5 = 150 attack
BOOST_MULTIPLIER = 1.5
