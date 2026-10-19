"""
Tests for common handlers.
"""
import copy
import json
import hashlib
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from faker import Faker
from opaque_keys.edx.keys import UsageKey
from xblock.field_data import DictFieldData
from xblock.fields import ScopeIds

from games.games import GamesXBlock
from games.handlers.common import CommonHandlers
from games.constants import GAME_TYPE, DEFAULT


class TestCommonHandlers(TestCase):
    """Tests for common handler methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.fake = Faker()
        self.runtime = Mock()
        usage_id = Mock()
        usage_id.block_id = self.fake.uuid4()
        self.scope_ids = ScopeIds(self.fake.uuid4(), "games", self.fake.uuid4(), usage_id)
        self.field_data = DictFieldData({
            'game_type': GAME_TYPE.FLASHCARDS,
            'cards': [],
            'is_shuffled': self.fake.boolean(),
            'has_timer': self.fake.boolean(),
            'display_name': self.fake.catch_phrase(),
        })
        self.xblock = GamesXBlock(self.runtime, self.field_data, self.scope_ids)

    # Tests for generate_unique_var_names
    def test_generate_unique_var_names(self):
        """Test generating unique variable names for obfuscation."""
        keys = [self.fake.word(), self.fake.word(), self.fake.word()]
        names = CommonHandlers.generate_unique_var_names(keys)

        self.assertEqual(len(names), 3)
        for key in keys:
            self.assertIn(key, names)

        # Check all names are unique
        values = list(names.values())
        self.assertEqual(len(values), len(set(values)))

        # Check name lengths
        for name in values:
            self.assertGreaterEqual(len(name), 3)
            self.assertLessEqual(len(name), 6)
            self.assertTrue(name.islower())

    # Tests for generate_encryption_key
    def test_generate_encryption_key(self):
        """Test encryption key generation."""
        key = CommonHandlers.generate_encryption_key(self.xblock)

        self.assertIsInstance(key, bytes)
        self.assertEqual(len(key), 44)  # Base64-encoded 32-byte key

    # Tests for encrypt_data and decrypt_data
    def test_encrypt_decrypt_data(self):
        """Test encrypting and decrypting data."""
        key = CommonHandlers.generate_encryption_key(self.xblock)
        original_data = {'term': self.fake.word(), 'definition': self.fake.sentence(), 'index': self.fake.random_int()}

        encrypted = CommonHandlers.encrypt_data(original_data, key)
        self.assertIsInstance(encrypted, str)
        self.assertNotEqual(encrypted, json.dumps(original_data))

        decrypted = CommonHandlers.decrypt_data(encrypted, key)
        self.assertEqual(decrypted, original_data)

    # Tests for get_settings
    def test_get_settings(self):
        """Test getting game settings."""
        self.xblock.game_type = GAME_TYPE.MATCHING
        cards = [{'term': self.fake.word(), 'definition': self.fake.word()}]
        is_shuffled = self.fake.boolean()
        has_timer = self.fake.boolean()
        self.xblock.cards = cards
        self.xblock.is_shuffled = is_shuffled
        self.xblock.has_timer = has_timer

        result = CommonHandlers.get_settings(self.xblock, {})

        self.assertEqual(result['game_type'], GAME_TYPE.MATCHING)
        self.assertEqual(result['cards'], cards)
        self.assertEqual(result['is_shuffled'], is_shuffled)
        self.assertEqual(result['has_timer'], has_timer)

    # Tests for decks
    def test_get_settings_synthesizes_deck_1_for_a_legacy_block(self):
        """A cards-only block must answer every client with the same one-deck shape."""
        cards = [{'term': self.fake.word(), 'definition': self.fake.sentence(), 'card_key': self.fake.uuid4()}]
        self.xblock.cards = cards

        result = CommonHandlers.get_settings(self.xblock, {})

        self.assertEqual(result['cards'], cards)
        self.assertEqual(len(result['decks']), 1)
        deck = result['decks'][0]
        self.assertEqual(deck['name'], 'Deck 1')
        self.assertEqual(deck['cards'], cards)
        self.assertTrue(deck['deck_key'])

    def test_synthesized_deck_key_is_stable_and_derived_from_the_usage_id(self):
        """Reading a legacy block must not invent a new deck key, and it must not write."""
        usage_id = UsageKey.from_string('block-v1:Org+Course+Run+type@games+block@deck-key-test')
        block = GamesXBlock(self.runtime, DictFieldData({}), ScopeIds('user', 'games', 'def', usage_id))

        first = CommonHandlers.get_settings(block, {})['decks'][0]['deck_key']
        second = CommonHandlers.get_settings(block, {})['decks'][0]['deck_key']
        self.assertEqual(first, second)
        self.assertEqual(block.decks, [])

        same_block = GamesXBlock(self.runtime, DictFieldData({}), ScopeIds('user', 'games', 'def', usage_id))
        other_block = GamesXBlock(
            self.runtime,
            DictFieldData({}),
            ScopeIds('user', 'games', 'def', UsageKey.from_string('block-v1:Org+Course+Run+type@games+block@other')),
        )
        self.assertEqual(CommonHandlers.get_settings(same_block, {})['decks'][0]['deck_key'], first)
        self.assertNotEqual(CommonHandlers.get_settings(other_block, {})['decks'][0]['deck_key'], first)

    def test_get_settings_returns_stored_decks(self):
        """Once decks exist they are returned as stored."""
        decks = [
            {'deck_key': self.fake.uuid4(), 'name': 'Deck 1', 'cards': []},
            {'deck_key': self.fake.uuid4(), 'name': 'Deck 2', 'cards': [{'term': 't', 'definition': 'd', 'card_key': 'k'}]},
        ]
        self.xblock.decks = decks

        result = CommonHandlers.get_settings(self.xblock, {})

        self.assertEqual(result['decks'], decks)
        self.assertEqual(result['decks'][1]['name'], 'Deck 2')

    # Tests for upload_image
    @patch('games.handlers.common.get_gamesxblock_storage')
    def test_upload_image_success(self, mock_get_storage):
        """Test successful image upload."""
        mock_storage = Mock()
        image_path = self.fake.file_path(extension='jpg')
        image_url = self.fake.image_url()
        mock_storage.save.return_value = image_path
        mock_storage.url.return_value = image_url
        mock_get_storage.return_value = mock_storage

        mock_file = Mock()
        mock_file.read.return_value = self.fake.binary(length=100)

        filename = self.fake.file_name(extension='jpg')
        mock_file_obj = Mock()
        mock_file_obj.file = mock_file
        mock_file_obj.filename = filename

        request = Mock()
        request.params = {'file': mock_file_obj}

        response = CommonHandlers.upload_image(self.xblock, request)

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.body.decode())
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['url'], image_url)
        self.assertEqual(response_data['filename'], filename)

    @patch('games.handlers.common.get_gamesxblock_storage')
    def test_upload_image_returns_the_key_storage_used(self, mock_get_storage):
        """Storage may rename on collision; the key handed back must be the real one."""
        mock_storage = Mock()
        mock_storage.save.return_value = f"games/{self.scope_ids.usage_id.block_id}/renamed_by_storage.png"
        mock_storage.url.return_value = "http://example.com/renamed_by_storage.png"
        mock_get_storage.return_value = mock_storage
        mock_file = Mock()
        mock_file.read.return_value = b"bytes"
        upload = Mock()
        upload.file = mock_file
        upload.filename = "image.png"
        request = Mock()
        request.params = {"file": upload}

        response = CommonHandlers.upload_image(self.xblock, request)

        body = json.loads(response.body)
        self.assertTrue(body["success"])
        self.assertEqual(body["file_path"], mock_storage.save.return_value)

    @patch('games.handlers.common.get_gamesxblock_storage')
    def test_upload_image_no_extension(self, mock_get_storage):
        """Test upload fails when file has no extension."""
        mock_file_obj = Mock()
        mock_file_obj.file = Mock()
        mock_file_obj.filename = self.fake.word()

        request = Mock()
        request.params = {'file': mock_file_obj}

        response = CommonHandlers.upload_image(self.xblock, request)

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.body.decode())
        self.assertFalse(response_data['success'])
        self.assertIn('extension', response_data['error'])

    @patch('games.handlers.common.get_gamesxblock_storage')
    def test_upload_image_invalid_extension(self, mock_get_storage):
        """Test upload fails with unsupported file type."""
        mock_file_obj = Mock()
        mock_file_obj.file = Mock()
        mock_file_obj.filename = self.fake.file_name(extension='exe')

        request = Mock()
        request.params = {'file': mock_file_obj}

        response = CommonHandlers.upload_image(self.xblock, request)

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.body.decode())
        self.assertFalse(response_data['success'])
        self.assertIn('Unsupported file type', response_data['error'])

    # Tests for save_settings
    def test_save_settings_flashcards(self):
        """Test saving settings for flashcards game."""
        display_name = self.fake.catch_phrase()
        data = {
            'game_type': GAME_TYPE.FLASHCARDS,
            'is_shuffled': self.fake.boolean(),
            'has_timer': self.fake.boolean(),
            'display_name': display_name,
            'cards': [
                {'term': self.fake.word(), 'definition': self.fake.sentence()},
                {'term': self.fake.word(), 'definition': self.fake.sentence()},
            ]
        }

        result = CommonHandlers.save_settings(self.xblock, data)

        self.assertTrue(result['success'])
        self.assertEqual(self.xblock.game_type, GAME_TYPE.FLASHCARDS)
        self.assertEqual(self.xblock.display_name, display_name)
        self.assertEqual(self.xblock.is_shuffled, data['is_shuffled'])
        self.assertEqual(self.xblock.has_timer, data['has_timer'])
        self.assertEqual(len(self.xblock.cards), 2)
        self.assertEqual(self.xblock.list_length, 2)

    def test_save_settings_matching(self):
        """Test saving settings for matching game."""
        data = {
            'game_type': GAME_TYPE.MATCHING,
            'is_shuffled': self.fake.boolean(),
            'has_timer': self.fake.boolean(),
            'display_name': self.fake.catch_phrase(),
            'cards': [
                {'term': self.fake.word(), 'definition': self.fake.sentence()},
            ]
        }

        result = CommonHandlers.save_settings(self.xblock, data)

        self.assertTrue(result['success'])
        self.assertEqual(self.xblock.game_type, GAME_TYPE.MATCHING)
        self.assertEqual(result['count'], 1)

    def test_save_settings_missing_required_fields(self):
        """Test save fails when cards missing required fields."""
        data = {
            'game_type': GAME_TYPE.FLASHCARDS,
            'cards': [
                {'term': self.fake.word()},  # Missing definition
            ]
        }

        result = CommonHandlers.save_settings(self.xblock, data)

        self.assertFalse(result['success'])
        self.assertIn('term and definition', result['error'])

    def test_save_settings_invalid_card_format(self):
        """Test save fails when card is not a dictionary."""
        data = {
            'game_type': GAME_TYPE.FLASHCARDS,
            'cards': [self.fake.sentence()]
        }

        result = CommonHandlers.save_settings(self.xblock, data)

        self.assertFalse(result['success'])
        self.assertIn('object', result['error'])

    def test_save_settings_with_decks_stores_them_and_mirrors_deck_1(self):
        """Decks are stored in order and the legacy cards field mirrors Deck 1."""
        card_key = self.fake.uuid4()
        deck_1_key = self.fake.uuid4()
        deck_2_key = self.fake.uuid4()
        payload = [
            {'deck_key': deck_1_key, 'name': 'Deck 1', 'cards': [
                {'term': 't1', 'definition': 'd1', 'card_key': card_key},
                {'term': 't2', 'definition': 'd2'},
            ]},
            {'deck_key': deck_2_key, 'name': 'Deck 2', 'cards': []},
        ]

        result = CommonHandlers.save_settings(self.xblock, {'game_type': GAME_TYPE.FLASHCARDS, 'decks': payload})

        self.assertTrue(result['success'])
        self.assertEqual([deck['deck_key'] for deck in self.xblock.decks], [deck_1_key, deck_2_key])
        self.assertEqual([deck['name'] for deck in self.xblock.decks], ['Deck 1', 'Deck 2'])
        self.assertEqual(self.xblock.decks[0]['cards'][0]['card_key'], card_key)
        self.assertEqual(self.xblock.cards, self.xblock.decks[0]['cards'])
        self.assertEqual(self.xblock.list_length, 2)
        self.assertEqual(result['decks'], self.xblock.decks)
        self.assertEqual(result['cards'], self.xblock.cards)
        self.assertEqual(result['count'], 2)

    def test_save_settings_assigns_keys_and_trims_deck_names(self):
        """A deck always ends up with a nonblank key and a trimmed name."""
        result = CommonHandlers.save_settings(self.xblock, {
            'game_type': GAME_TYPE.FLASHCARDS,
            'decks': [
                {'name': '  Deck A  ', 'cards': [{'term': 't', 'definition': 'd', 'card_key': ''}]},
                {'deck_key': '', 'name': 'Deck B', 'cards': [{'term': 't', 'definition': 'd', 'card_key': 5}]},
                {'deck_key': 7, 'name': 'Deck C', 'cards': [{'term': 't', 'definition': 'd', 'card_key': 'kept-key'}]},
            ],
        })

        self.assertTrue(result['success'])
        self.assertEqual([deck['name'] for deck in self.xblock.decks], ['Deck A', 'Deck B', 'Deck C'])
        deck_keys = [deck['deck_key'] for deck in self.xblock.decks]
        self.assertEqual(len(set(deck_keys)), 3)
        self.assertTrue(all(isinstance(key, str) and key for key in deck_keys))
        card_keys = [deck['cards'][0]['card_key'] for deck in self.xblock.decks]
        self.assertEqual(card_keys[2], 'kept-key')
        self.assertTrue(all(card_key for card_key in card_keys))
        self.assertEqual(len(set(card_keys)), 3)

    def test_save_settings_cards_only_updates_deck_1_and_keeps_the_others(self):
        """An older client must not lose decks it does not know about."""
        stored = [
            {'deck_key': 'deck-1-key', 'name': 'Deck 1', 'cards': [{'term': 'old', 'definition': 'x', 'card_key': 'c1'}]},
            {'deck_key': 'deck-2-key', 'name': 'Deck 2', 'cards': [{'term': 'keep', 'definition': 'y', 'card_key': 'c2'}]},
        ]
        untouched = copy.deepcopy(stored)
        self.xblock.decks = stored
        self.xblock.cards = stored[0]['cards']

        result = CommonHandlers.save_settings(self.xblock, {
            'game_type': GAME_TYPE.FLASHCARDS,
            'cards': [{'term': 'new', 'definition': 'z', 'card_key': 'c3'}],
        })

        self.assertTrue(result['success'])
        self.assertEqual(len(self.xblock.decks), 2)
        self.assertEqual(self.xblock.decks[0]['deck_key'], 'deck-1-key')
        self.assertEqual(self.xblock.decks[0]['name'], 'Deck 1')
        self.assertEqual(self.xblock.decks[0]['cards'][0]['term'], 'new')
        self.assertEqual(self.xblock.decks[0]['cards'][0]['card_key'], 'c3')
        self.assertEqual(self.xblock.decks[1], untouched[1])
        self.assertEqual(self.xblock.cards, self.xblock.decks[0]['cards'])
        self.assertEqual(self.xblock.list_length, 1)
        self.assertEqual(result['decks'], self.xblock.decks)

    def test_save_settings_cards_only_rejects_duplicate_card_keys_within_deck_1(self):
        """A flat cards save must not create duplicate card keys in Deck 1."""
        self.xblock.decks = self._stored_decks()
        self.xblock.cards = self.xblock.decks[0]['cards']
        self.xblock.list_length = 1
        stored = copy.deepcopy(self.xblock.decks)

        result = CommonHandlers.save_settings(self.xblock, {
            'game_type': GAME_TYPE.FLASHCARDS,
            'cards': [
                {'term': 'a', 'definition': 'b', 'card_key': 'same-key'},
                {'term': 'c', 'definition': 'd', 'card_key': 'same-key'},
            ],
        })

        self.assertFalse(result['success'])
        self.assertIn('card_key', result['error'])
        self.assertEqual(self.xblock.decks, stored)
        self.assertEqual(self.xblock.cards, stored[0]['cards'])
        self.assertEqual(self.xblock.list_length, 1)

    def test_save_settings_cards_only_rejects_card_key_conflict_with_a_preserved_deck(self):
        """A flat cards save must not duplicate a key already in Deck 2."""
        stored = [
            {'deck_key': 'deck-1-key', 'name': 'Deck 1', 'cards': []},
            {'deck_key': 'deck-2-key', 'name': 'Deck 2', 'cards': [
                {'term': 'keep', 'definition': 'y', 'card_key': 'shared-key'},
            ]},
        ]
        self.xblock.decks = copy.deepcopy(stored)
        self.xblock.cards = self.xblock.decks[0]['cards']
        self.xblock.list_length = 0
        before = copy.deepcopy(self.xblock.decks)

        result = CommonHandlers.save_settings(self.xblock, {
            'game_type': GAME_TYPE.FLASHCARDS,
            'cards': [{'term': 'new', 'definition': 'z', 'card_key': 'shared-key'}],
        })

        self.assertFalse(result['success'])
        self.assertIn('card_key', result['error'])
        self.assertEqual(self.xblock.decks, before)
        self.assertEqual(self.xblock.cards, before[0]['cards'])
        self.assertEqual(self.xblock.list_length, 0)

    def test_save_settings_cards_only_materializes_deck_1_for_a_legacy_block(self):
        """The deck a legacy block was shown must be the deck it saves into."""
        before = CommonHandlers.get_settings(self.xblock, {})['decks'][0]['deck_key']

        result = CommonHandlers.save_settings(self.xblock, {
            'game_type': GAME_TYPE.FLASHCARDS,
            'cards': [{'term': 't', 'definition': 'd'}],
        })

        self.assertTrue(result['success'])
        self.assertEqual(len(self.xblock.decks), 1)
        self.assertEqual(self.xblock.decks[0]['deck_key'], before)
        self.assertEqual(self.xblock.decks[0]['name'], 'Deck 1')
        self.assertEqual(self.xblock.decks[0]['cards'], self.xblock.cards)
        self.assertEqual(self.xblock.list_length, 1)

    def test_save_settings_prefers_decks_when_both_shapes_are_sent(self):
        """The explicit deck list is authoritative; the flat cards are ignored."""
        result = CommonHandlers.save_settings(self.xblock, {
            'game_type': GAME_TYPE.FLASHCARDS,
            'decks': [{'deck_key': 'd', 'name': 'Deck 1', 'cards': [{'term': 'from-decks', 'definition': 'd'}]}],
            'cards': [{'term': 'from-cards', 'definition': 'd'}],
        })

        self.assertTrue(result['success'])
        self.assertEqual(len(self.xblock.decks), 1)
        self.assertEqual(len(self.xblock.decks[0]['cards']), 1)
        self.assertEqual(len(self.xblock.cards), 1)
        self.assertEqual([card['term'] for card in self.xblock.cards], ['from-decks'])
        self.assertEqual(self.xblock.cards, self.xblock.decks[0]['cards'])

    def _stored_decks(self):
        """Two stored decks, to prove failed saves leave them alone."""
        return [
            {'deck_key': 'deck-1-key', 'name': 'Deck 1', 'cards': [{'term': 'a', 'definition': 'b', 'card_key': 'c1'}]},
            {'deck_key': 'deck-2-key', 'name': 'Deck 2', 'cards': []},
        ]

    def test_save_settings_rejects_empty_decks(self):
        """A block must always keep at least one deck."""
        self.xblock.decks = self._stored_decks()
        self.xblock.cards = self.xblock.decks[0]['cards']

        result = CommonHandlers.save_settings(self.xblock, {'decks': []})

        self.assertFalse(result['success'])
        self.assertEqual(self.xblock.decks, self._stored_decks())
        self.assertEqual(self.xblock.cards, self._stored_decks()[0]['cards'])

    def test_save_settings_rejects_blank_and_duplicate_deck_names(self):
        """Names are required and unique ignoring case, whitespace included."""
        self.xblock.decks = self._stored_decks()
        bad_name_lists = [
            [{'name': '   ', 'cards': []}],
            [{'name': '', 'cards': []}],
            [{'name': None, 'cards': []}],
            [{'name': 'Deck A', 'cards': []}, {'name': '  deck a  ', 'cards': []}],
        ]
        for decks in bad_name_lists:
            result = CommonHandlers.save_settings(self.xblock, {'decks': decks})
            self.assertFalse(result['success'], decks)
            self.assertEqual(self.xblock.decks, self._stored_decks(), decks)

    def test_save_settings_rejects_duplicate_deck_and_card_keys(self):
        """Keys identify decks and cards across the whole block."""
        self.xblock.decks = self._stored_decks()
        bad_decks = [
            [
                {'deck_key': 'same', 'name': 'Deck A', 'cards': []},
                {'deck_key': 'same', 'name': 'Deck B', 'cards': []},
            ],
            [
                {'name': 'Deck A', 'cards': [{'term': 't', 'definition': 'd', 'card_key': 'same'}]},
                {'name': 'Deck B', 'cards': [{'term': 't', 'definition': 'd', 'card_key': 'same'}]},
            ],
            [
                {'name': 'Deck A', 'cards': [
                    {'term': 't', 'definition': 'd', 'card_key': 'same'},
                    {'term': 't', 'definition': 'd', 'card_key': 'same'},
                ]},
            ],
        ]
        for decks in bad_decks:
            result = CommonHandlers.save_settings(self.xblock, {'decks': decks})
            self.assertFalse(result['success'], decks)
            self.assertEqual(self.xblock.decks, self._stored_decks(), decks)

    def test_save_settings_validates_every_deck_and_writes_nothing_on_failure(self):
        """A bad card in the last deck must reject the whole payload."""
        self.xblock.decks = self._stored_decks()
        self.xblock.cards = self.xblock.decks[0]['cards']
        self.xblock.list_length = 1

        result = CommonHandlers.save_settings(self.xblock, {
            'decks': [
                {'name': 'Deck A', 'cards': [{'term': 'ok', 'definition': 'ok'}]},
                {'name': 'Deck B', 'cards': [{'term': 'missing definition'}]},
            ],
        })

        self.assertFalse(result['success'])
        self.assertIn('term and definition', result['error'])
        self.assertEqual(self.xblock.decks, self._stored_decks())
        self.assertEqual(self.xblock.cards, self._stored_decks()[0]['cards'])
        self.assertEqual(self.xblock.list_length, 1)

    def test_save_settings_applies_image_path_rules_to_every_deck(self):
        """Storage keys are only kept for this block, in any deck."""
        own_path = f"games/{self.scope_ids.usage_id.block_id}/ok.png"

        result = CommonHandlers.save_settings(self.xblock, {
            'decks': [
                {'name': 'Deck A', 'cards': []},
                {'name': 'Deck B', 'cards': [
                    {'term': 't', 'definition': 'd', 'term_image_path': own_path,
                     'definition_image_path': 'games/other-block/x.png'},
                ]},
            ],
        })

        self.assertTrue(result['success'])
        card = self.xblock.decks[1]['cards'][0]
        self.assertEqual(card['term_image_path'], own_path)
        self.assertEqual(card['definition_image_path'], '')

    def test_save_settings_rejects_a_deck_whose_cards_are_not_a_list(self):
        """Decks carry ordered card lists; anything else is a client bug."""
        self.xblock.decks = self._stored_decks()

        result = CommonHandlers.save_settings(self.xblock, {'decks': [{'name': 'Deck A', 'cards': 'nope'}]})

        self.assertFalse(result['success'])
        self.assertEqual(self.xblock.decks, self._stored_decks())

    def test_save_settings_rejects_a_deck_without_a_cards_key(self):
        """The frozen deck shape requires cards, even when the list is empty."""
        self.xblock.decks = self._stored_decks()
        self.xblock.cards = self.xblock.decks[0]['cards']
        self.xblock.list_length = 1
        before = copy.deepcopy(self.xblock.decks)

        result = CommonHandlers.save_settings(self.xblock, {
            'decks': [{'deck_key': 'deck-1-key', 'name': 'Deck 1'}],
        })

        self.assertFalse(result['success'])
        self.assertIn('cards', result['error'])
        self.assertEqual(self.xblock.decks, before)
        self.assertEqual(self.xblock.cards, before[0]['cards'])
        self.assertEqual(self.xblock.list_length, 1)

    # Tests for format_as_uuid_like
    def test_format_as_uuid_like(self):
        """Test UUID-like formatting for obfuscation."""
        key_hex = self.fake.hexify(text='^^^^^^^^', upper=False)
        index = self.fake.random_int(min=0, max=1000)

        result = CommonHandlers.format_as_uuid_like(key_hex, index)

        # Check format: 8-4-4-4-12 (36 chars + 4 hyphens = 40 chars with hyphens)
        parts = result.split('-')
        self.assertEqual(len(parts), 5)
        self.assertEqual(len(parts[0]), 8)
        self.assertEqual(len(parts[1]), 4)
        self.assertEqual(len(parts[2]), 4)
        self.assertEqual(len(parts[3]), 4)
        self.assertEqual(len(parts[4]), 12)

        # First part should be the key
        self.assertEqual(parts[0], key_hex)

    # Tests for delete_image_handler
    @patch('games.handlers.common.get_gamesxblock_storage')
    @patch('games.handlers.common.delete_image')
    def test_delete_image_handler_success(self, mock_delete, mock_get_storage):
        """Test successful image deletion."""
        mock_delete.return_value = True
        mock_storage = Mock()
        mock_get_storage.return_value = mock_storage

        image_key = f"games/{self.scope_ids.usage_id.block_id}/{self.fake.md5()}.jpg"
        data = {'key': image_key}
        result = CommonHandlers.delete_image_handler(self.xblock, data)

        self.assertTrue(result['success'])
        self.assertEqual(result['key'], image_key)
        mock_delete.assert_called_once_with(mock_storage, image_key)

    @patch('games.handlers.common.get_gamesxblock_storage')
    @patch('games.handlers.common.delete_image')
    def test_delete_image_handler_rejects_key_of_another_block(self, mock_delete, mock_get_storage):
        """The bucket is shared platform-wide; only this block's own keys may be deleted."""
        for bad_key in (
            "games/otherblock/abc.jpg",
            f"games/{self.scope_ids.usage_id.block_id}/../abc.jpg",
            f"games/{self.scope_ids.usage_id.block_id}/notes.txt",
            self.fake.file_path(extension='jpg'),
        ):
            result = CommonHandlers.delete_image_handler(self.xblock, {'key': bad_key})
            self.assertFalse(result['success'], bad_key)
        mock_delete.assert_not_called()

    @patch('games.handlers.common.get_gamesxblock_storage')
    def test_delete_image_handler_missing_key(self, mock_get_storage):
        """Test delete fails when key is missing."""
        data = {}
        result = CommonHandlers.delete_image_handler(self.xblock, data)

        self.assertFalse(result['success'])
        self.assertIn('Missing key', result['error'])
