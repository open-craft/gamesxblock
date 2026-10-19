"""
Constants for the Games XBlock.

This module contains all constant values used throughout the Games XBlock,
including game types, field names, default values, error messages, and UI text.
"""


class GAME_TYPE:
    """Game type constants."""

    FLASHCARDS = "flashcards"
    MATCHING = "matching"
    VALID = [FLASHCARDS, MATCHING]


class DEFAULT:
    """Default values for XBlock fields."""

    MATCHING_TITLE = "Matching"
    FLASHCARDS_TITLE = "Flashcards"
    DISPLAY_NAME = "Games"
    GAME_TYPE = GAME_TYPE.FLASHCARDS
    IS_SHUFFLED = True
    HAS_TIMER = True
    DECK_NAME = "Deck 1"


class DECK_FIELD:
    """Deck field names."""

    DECK_KEY = "deck_key"
    NAME = "name"
    CARDS = "cards"


class CARD_FIELD:
    """Card field names."""

    CARD_KEY = "card_key"
    TERM = "term"
    TERM_IMAGE = "term_image"
    DEFINITION = "definition"
    DEFINITION_IMAGE = "definition_image"
    ORDER = "order"
    TERM_IMAGE_ALT = "term_image_alt"
    DEFINITION_IMAGE_ALT = "definition_image_alt"
    TERM_IMAGE_PATH = "term_image_path"
    DEFINITION_IMAGE_PATH = "definition_image_path"


class CONTAINER_TYPE:
    """Container types for matching game."""

    TERM = "term"
    DEFINITION = "definition"


class UPLOAD:
    """File upload settings."""

    PATH_PREFIX = "games"
    ALLOWED_EXTENSIONS = ("jpg", "jpeg", "png", "gif", "webp", "svg")


class CONFIG:
    """Configuration values."""

    RANDOM_STRING_LENGTH = 8
    SALT_LENGTH = 12  # Length of random salt added to obfuscated payloads
    MATCHES_PER_PAGE = 5  # Number of matches displayed per page
    ENCRYPTION_SALT = "gamesxblock_secure_salt_v1"  # Salt for encryption key generation
