"""
Constants used throughout the protocol.
All the message types and other values we use are defined here.
"""


class MessageType:
    """All the different message types in our protocol."""

    # connection messages
    HANDSHAKE_REQUEST = "HANDSHAKE_REQUEST"
    HANDSHAKE_RESPONSE = "HANDSHAKE_RESPONSE"
    SPECTATOR_REQUEST = "SPECTATOR_REQUEST"

    # battle setup
    BATTLE_SETUP = "BATTLE_SETUP"

    # battle messages (the 4-step handshake)
    ATTACK_ANNOUNCE = "ATTACK_ANNOUNCE"
    DEFENSE_ANNOUNCE = "DEFENSE_ANNOUNCE"
    CALCULATION_REPORT = "CALCULATION_REPORT"
    CALCULATION_CONFIRM = "CALCULATION_CONFIRM"

    # when calculations dont match
    RESOLUTION_REQUEST = "RESOLUTION_REQUEST"

    # end of game
    GAME_OVER = "GAME_OVER"

    # chat
    CHAT_MESSAGE = "CHAT_MESSAGE"

    # for reliability
    ACK = "ACK"


class ContentType:
    """Types of chat content - either text or sticker."""

    TEXT = "TEXT"
    STICKER = "STICKER"


class CommunicationMode:
    """How peers talk to each other - P2P or broadcast."""

    P2P = "P2P"
    BROADCAST = "BROADCAST"


# timing stuff
ACK_TIMEOUT_SECONDS = 0.5  # how long to wait for ACK
MAX_RETRIES = 3  # how many times to retry

# battle stuff
DEFAULT_SPECIAL_ATTACK_USES = 5
DEFAULT_SPECIAL_DEFENSE_USES = 5
BOOST_MULTIPLIER = 1.5
