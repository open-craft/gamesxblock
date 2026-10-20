"""
Common handler methods for the Games XBlock.
"""

import base64
import hashlib
import json
import random
import string
import uuid

from django.core.files.base import ContentFile
from django.utils.translation import gettext as _
from xblock.core import Response
from cryptography.fernet import Fernet

from games.utils import delete_image, get_gamesxblock_storage

from ..constants import CARD_FIELD, CONFIG, DEFAULT, DECK_FIELD, GAME_TYPE, UPLOAD


class CommonHandlers:
    """Handlers that work across all game types."""

    @staticmethod
    def generate_unique_var_names(keys, min_len=3, max_len=6, max_attempts=1000):
        """
        Generate unique random variable names for obfuscation.
        """
        used = set()
        names = {}
        for key in keys:
            for _ in range(max_attempts):
                name = "".join(random.choices(string.ascii_lowercase, k=random.randint(min_len, max_len)))
                if name not in used:
                    used.add(name)
                    names[key] = name
                    break
            else:
                raise RuntimeError(f"Unable to generate a unique variable name after {max_attempts} attempts. Consider increasing min_len/max_len.")
        return names

    @staticmethod
    def generate_encryption_key(xblock):
        """
        Generate encryption key using block_id and salt.
        Uses a consistent identifier that doesn't change across requests.

        Args:
            xblock: The xblock instance

        Returns:
            Base64-encoded encryption key (bytes)
        """
        # Use block_id (which is stable) and the encryption salt
        block_id = str(xblock.scope_ids.usage_id.block_id)
        seed_string = f"{block_id}:{CONFIG.ENCRYPTION_SALT}"

        # Generate a 32-byte key using SHA-256
        key_bytes = hashlib.sha256(seed_string.encode()).digest()

        # Fernet requires base64-encoded 32-byte key
        return base64.urlsafe_b64encode(key_bytes)

    @staticmethod
    def encrypt_data(data, encryption_key):
        """
        Encrypt data using Fernet (symmetric encryption).

        Args:
            data: Dictionary or any JSON-serializable data to encrypt
            encryption_key: Base64-encoded encryption key

        Returns:
            Base64-encoded encrypted string
        """
        fernet = Fernet(encryption_key)
        data_json = json.dumps(data)
        encrypted_data = fernet.encrypt(data_json.encode())
        return encrypted_data.decode()

    @staticmethod
    def decrypt_data(encrypted_hash, encryption_key):
        """
        Decrypt encrypted data back to original format.

        Args:
            encrypted_hash: Base64-encoded encrypted string
            encryption_key: Base64-encoded encryption key

        Returns:
            Decrypted data (dictionary or original data structure)
        """
        fernet = Fernet(encryption_key)
        # Fernet.decrypt expects bytes (base64-encoded), so just encode the string
        decrypted_json = fernet.decrypt(encrypted_hash.encode()).decode()
        return json.loads(decrypted_json)

    @staticmethod
    def deck_one_key(xblock):
        """
        Stable key for the implicit Deck 1 of a cards-only block.

        Derived from the usage id so that reading a legacy block does not invent
        a new key and a later save materializes the same deck.
        """
        block_id = str(xblock.scope_ids.usage_id.block_id)
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"games/deck-1/{block_id}"))

    @staticmethod
    def primary_cards(decks):
        """
        Cards of the first deck, the primary deck older clients call ``cards``.

        Always read from the deck list, so a stale or absent ``cards`` mirror
        cannot change what clients see. A malformed stored value counts as none.
        """
        primary = decks[0] if decks else None
        if not isinstance(primary, dict):
            return []
        cards = primary.get(DECK_FIELD.CARDS)
        return list(cards) if isinstance(cards, list) else []

    @staticmethod
    def get_decks(xblock):
        """
        Decks to hand to clients.

        A block authored before decks existed has none stored, so its cards are
        presented as Deck 1. That is read-only; nothing is written until a save.
        """
        if xblock.decks:
            # Returned as stored; get_settings derives the cards mirror from the
            # first deck, so a stale mirror never reaches a client.
            return xblock.decks
        return [
            {
                DECK_FIELD.DECK_KEY: CommonHandlers.deck_one_key(xblock),
                DECK_FIELD.NAME: DEFAULT.DECK_NAME,
                # OLX with an empty cards attribute parses as None, not [].
                DECK_FIELD.CARDS: xblock.cards or [],
            }
        ]

    @staticmethod
    def get_settings(xblock, data, suffix=""):
        """Get game type, decks, the primary deck's cards, and settings in one call."""
        decks = CommonHandlers.get_decks(xblock)
        return {
            "game_type": xblock.game_type,
            "decks": decks,
            # Compatibility view of the first deck, never a separate source of truth.
            "cards": CommonHandlers.primary_cards(decks),
            "is_shuffled": xblock.is_shuffled,
            "has_timer": xblock.has_timer,
        }

    @staticmethod
    def upload_image(xblock, request, suffix=""):
        """
        Upload an image file to configured storage (S3 if set) and return URL.
        """
        asset_storage = get_gamesxblock_storage()
        try:
            upload_file = request.params["file"].file
            file_name = request.params["file"].filename
            if "." not in file_name:
                return Response(
                    json_body={
                        "success": False,
                        "error": "File must have an extension",
                    },
                    status=400,
                )
            _stem, ext = file_name.rsplit(".", 1)
            ext = ext.lower()
            if ext not in UPLOAD.ALLOWED_EXTENSIONS:
                return Response(
                    json_body={
                        "success": False,
                        "error": (
                            f"Unsupported file type '.{ext}'. "
                            f"Allowed: {', '.join(sorted(UPLOAD.ALLOWED_EXTENSIONS))}"
                        ),
                    },
                    status=400,
                )
            blob = upload_file.read()
            file_hash = hashlib.md5(blob).hexdigest()
            file_path = f"{UPLOAD.PATH_PREFIX}/{xblock.scope_ids.usage_id.block_id}/{file_hash}.{ext}"
            saved_path = asset_storage.save(file_path, ContentFile(blob))
            file_url = asset_storage.url(saved_path)
            return Response(
                json_body={
                    "success": True,
                    "url": file_url,
                    "filename": file_name,
                    "file_path": saved_path,
                }
            )
        except Exception as e:
            return Response(json_body={"success": False, "error": str(e)}, status=400)

    @staticmethod
    def delete_image_handler(xblock, data, suffix=""):
        """
        Delete an image by storage key.
        Expected: { "key": "games/<block_id>/<hash>.ext" }

        Only keys this block created through ``upload_image`` are accepted; the
        storage bucket is shared platform-wide.
        """
        raw_key = data.get("key")
        if not raw_key:
            return {"success": False, "error": "Missing key"}
        key = CommonHandlers.own_storage_key(xblock, raw_key)
        if not key:
            return {"success": False, "error": _("Key does not belong to this block")}
        try:
            storage = get_gamesxblock_storage()
            is_deleted = delete_image(storage, key)
            return {"success": is_deleted, "key": key}
        except Exception:  # pylint: disable=broad-exception-caught
            return {"success": False, "error": _("Delete failed")}

    @staticmethod
    def own_storage_key(xblock, key):
        """
        Return ``key`` only if it is a storage key this block created through
        ``upload_image`` (``<UPLOAD.PATH_PREFIX>/<block_id>/<file>``); otherwise "".

        The client supplies these keys and they are meant to drive a later
        cleanup/delete, so a key pointing at another block's file (or any
        arbitrary storage path) must not be persisted.
        """
        if not isinstance(key, str) or not key:
            return ""
        prefix = f"{UPLOAD.PATH_PREFIX}/{xblock.scope_ids.usage_id.block_id}/"
        name = key[len(prefix):]
        if not key.startswith(prefix) or not name or "/" in name or "\\" in name or name in (".", ".."):
            return ""
        if name.rsplit(".", 1)[-1].lower() not in UPLOAD.ALLOWED_EXTENSIONS:
            return ""
        return key

    @staticmethod
    def text_field(value, default=""):
        """
        Return ``value`` if it is a string, else ``default``.

        Card text fields come from the client; a ``null`` or non-string value
        stored here makes ``student_view`` raise for every learner
        (``.strip()`` / ``.encode()`` on ``None``), so coerce at the boundary.
        """
        return value if isinstance(value, str) else default

    @staticmethod
    def validate_cards(xblock, new_cards):
        """
        Canonicalize one deck's card list, raising ValueError on bad input.

        Applies the same rules the flat-card save has always applied: text
        fields are coerced, a missing key is assigned, only storage keys this
        block created are kept, and ``order`` becomes the array index because
        array position is authoritative.
        """
        if not isinstance(new_cards, list):
            raise ValueError(_("cards must be a list"))

        validated_cards = []
        for index, card in enumerate(new_cards):
            if not isinstance(card, dict):
                raise ValueError(_("Each card must be an object"))

            # Validate required fields
            if CARD_FIELD.TERM not in card or CARD_FIELD.DEFINITION not in card:
                raise ValueError(_("Each card must have term and definition"))

            card_key = card.get(CARD_FIELD.CARD_KEY)
            if not isinstance(card_key, str) or not card_key.strip():
                card_key = str(uuid.uuid4())

            validated_cards.append(
                {
                    CARD_FIELD.TERM: CommonHandlers.text_field(card.get(CARD_FIELD.TERM)),
                    CARD_FIELD.TERM_IMAGE: CommonHandlers.text_field(card.get(CARD_FIELD.TERM_IMAGE)),
                    CARD_FIELD.DEFINITION: CommonHandlers.text_field(card.get(CARD_FIELD.DEFINITION)),
                    CARD_FIELD.DEFINITION_IMAGE: CommonHandlers.text_field(card.get(CARD_FIELD.DEFINITION_IMAGE)),
                    CARD_FIELD.ORDER: index,
                    CARD_FIELD.CARD_KEY: card_key,
                    CARD_FIELD.TERM_IMAGE_ALT: CommonHandlers.text_field(card.get(CARD_FIELD.TERM_IMAGE_ALT)),
                    CARD_FIELD.DEFINITION_IMAGE_ALT: CommonHandlers.text_field(
                        card.get(CARD_FIELD.DEFINITION_IMAGE_ALT)
                    ),
                    # Storage keys: where each image's file lives, as opposed to
                    # the URL it is shown from. Kept so the block knows which file
                    # belongs to a card (a cleanup of unused files needs that).
                    CARD_FIELD.TERM_IMAGE_PATH: CommonHandlers.own_storage_key(
                        xblock, card.get(CARD_FIELD.TERM_IMAGE_PATH, "")
                    ),
                    CARD_FIELD.DEFINITION_IMAGE_PATH: CommonHandlers.own_storage_key(
                        xblock, card.get(CARD_FIELD.DEFINITION_IMAGE_PATH, "")
                    ),
                }
            )

        return validated_cards

    @staticmethod
    def ensure_unique_card_keys(decks):
        """Raise when a card_key repeats across the candidate decks."""
        seen = set()
        for deck in decks:
            for card in deck.get(DECK_FIELD.CARDS) or []:
                card_key = card[CARD_FIELD.CARD_KEY]
                if card_key in seen:
                    raise ValueError(_("Duplicate card_key"))
                seen.add(card_key)

    @staticmethod
    def validate_decks(xblock, new_decks):
        """
        Canonicalize a client's deck list, raising ValueError on bad input.

        Every deck keeps its position, gets a nonblank key and a trimmed,
        case-insensitively unique name. Deck and card keys must be unique across
        all decks, and every card is validated with the flat-card rules.
        """
        if not isinstance(new_decks, list):
            raise ValueError(_("decks must be a list"))
        if not new_decks:
            raise ValueError(_("At least one deck is required"))

        validated_decks = []
        deck_keys = set()
        names = set()
        for deck in new_decks:
            if not isinstance(deck, dict):
                raise ValueError(_("Each deck must be an object"))

            raw_name = deck.get(DECK_FIELD.NAME)
            name = raw_name.strip() if isinstance(raw_name, str) else ""
            if not name:
                raise ValueError(_("Each deck must have a name"))
            if name.casefold() in names:
                raise ValueError(_("Deck names must be unique"))
            names.add(name.casefold())

            deck_key = deck.get(DECK_FIELD.DECK_KEY)
            if not isinstance(deck_key, str) or not deck_key.strip():
                deck_key = str(uuid.uuid4())
            if deck_key in deck_keys:
                raise ValueError(_("Duplicate deck_key"))
            deck_keys.add(deck_key)

            if DECK_FIELD.CARDS not in deck:
                raise ValueError(_("Each deck must have a cards list"))
            cards = CommonHandlers.validate_cards(xblock, deck[DECK_FIELD.CARDS])

            validated_decks.append(
                {
                    DECK_FIELD.DECK_KEY: deck_key,
                    DECK_FIELD.NAME: name,
                    DECK_FIELD.CARDS: cards,
                }
            )

        CommonHandlers.ensure_unique_card_keys(validated_decks)
        return validated_decks

    @staticmethod
    def save_settings(xblock, data, suffix=""):
        """
        Save game type, settings, and content in one API call.

        Omitted top-level fields keep their current value. A payload with a decks
        key replaces the whole deck list, so omitted decks are deleted; decks wins
        when both decks and cards are sent. A payload with only cards is the older
        client shape: it updates the first deck and leaves every other deck
        untouched. A payload with neither leaves authored content alone. Study
        progress belongs to the browser and is never accepted here. Expected data
        format:
        {
            'display_name': 'Block title',
            'game_type': 'flashcards' or 'matching',
            'is_shuffled': true or false,
            'has_timer': true or false,
            'decks': [
                {
                    'deck_key': 'uuid (assigned here if missing)',
                    'name': 'Deck 1',
                    'cards': [ ... card objects ... ],
                },
                ...
            ],
            'cards': [ ... card objects ... ]  # legacy shape, Deck 1 only
        }
        """
        try:
            new_game_type = data.get("game_type", xblock.game_type)
            if new_game_type not in GAME_TYPE.VALID:
                return {"success": False, "error": _("Invalid game type")}
            new_is_shuffled = data.get("is_shuffled", xblock.is_shuffled)
            new_has_timer = data.get("has_timer", xblock.has_timer)
            if not isinstance(new_is_shuffled, bool) or not isinstance(new_has_timer, bool):
                return {"success": False, "error": _("is_shuffled and has_timer must be booleans")}
            display_name = CommonHandlers.text_field(data.get("display_name"), xblock.display_name)

            new_decks = None
            if "decks" in data:
                # The sent list is the complete deck list; omitted decks are deleted.
                new_decks = CommonHandlers.validate_decks(xblock, data["decks"])
            elif "cards" in data:
                new_cards = CommonHandlers.validate_cards(xblock, data["cards"])
                stored_decks = xblock.decks or []
                if stored_decks:
                    # Canonicalize the decks this save keeps, so an unvalidated card
                    # without a card_key cannot break an older client's save.
                    stored_decks = CommonHandlers.validate_decks(xblock, stored_decks)
                    new_decks = [{**stored_decks[0], DECK_FIELD.CARDS: new_cards}]
                    new_decks += stored_decks[1:]
                else:
                    new_decks = [
                        {
                            DECK_FIELD.DECK_KEY: CommonHandlers.deck_one_key(xblock),
                            DECK_FIELD.NAME: DEFAULT.DECK_NAME,
                            DECK_FIELD.CARDS: new_cards,
                        }
                    ]
                CommonHandlers.ensure_unique_card_keys(new_decks)
            elif xblock.decks:
                new_decks = list(xblock.decks)

            if new_decks:
                xblock.decks = new_decks
                # cards and list_length stay the compatibility view of the first deck.
                xblock.cards = CommonHandlers.primary_cards(new_decks)
                xblock.list_length = len(xblock.cards)

            xblock.display_name = display_name
            if "game_type" in data:
                xblock.title = (
                    DEFAULT.FLASHCARDS_TITLE
                    if new_game_type == GAME_TYPE.FLASHCARDS
                    else DEFAULT.MATCHING_TITLE
                )
            xblock.game_type = new_game_type
            xblock.is_shuffled = new_is_shuffled
            xblock.has_timer = new_has_timer

            xblock.save()

            # Same shape as get_settings: a legacy cards-only block answers with
            # its synthesized primary deck instead of an empty decks list.
            response_decks = CommonHandlers.get_decks(xblock)
            response_cards = CommonHandlers.primary_cards(response_decks)
            return {
                "success": True,
                "game_type": xblock.game_type,
                "decks": response_decks,
                "cards": response_cards,
                "count": len(response_cards),
                "is_shuffled": xblock.is_shuffled,
                "has_timer": xblock.has_timer,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def format_as_uuid_like(key_hex, index):
        """
        Format key and index as UUID-like string for maximum obfuscation.
        Format: key-index_part1-rand4-index_part2-rand12

        Args:
            key_hex: 8-char hex string (key)
            index: integer index

        Returns:
            UUID-like formatted string (36 chars total: 8-4-4-4-12)
        """
        index_hex = format(index, '08x')
        index_part1 = index_hex[:4]
        index_part2 = index_hex[4:]
        rand_4 = format(random.getrandbits(16), '04x')
        rand_12 = format(random.getrandbits(48), '012x')
        return f"{key_hex}-{index_part1}-{rand_4}-{index_part2}-{rand_12}"
