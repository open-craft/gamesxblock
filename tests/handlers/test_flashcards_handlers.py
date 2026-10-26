"""
Tests for flashcards and matching handlers.
"""
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from faker import Faker
from xblock.field_data import DictFieldData
from xblock.fields import ScopeIds

from games.games import GamesXBlock
from games.handlers.flashcards import FlashcardsHandlers
from games.constants import GAME_TYPE, CARD_FIELD
from games.utils import read_resource


class TestFlashcardsHandlers(TestCase):
    """Tests for flashcards handler methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.fake = Faker()
        self.runtime = Mock()
        self.scope_ids = ScopeIds(self.fake.uuid4(), "games", self.fake.uuid4(), self.fake.uuid4())
        self.title = self.fake.catch_phrase()
        self.field_data = DictFieldData({
            'game_type': GAME_TYPE.FLASHCARDS,
            'cards': [
                {CARD_FIELD.CARD_KEY: self.fake.uuid4(), CARD_FIELD.TERM: self.fake.word(), CARD_FIELD.DEFINITION: self.fake.sentence()},
                {CARD_FIELD.CARD_KEY: self.fake.uuid4(), CARD_FIELD.TERM: self.fake.word(), CARD_FIELD.DEFINITION: self.fake.sentence()},
            ],
            'is_shuffled': self.fake.boolean(),
            'has_timer': self.fake.boolean(),
            'title': self.title,
        })
        self.xblock = GamesXBlock(self.runtime, self.field_data, self.scope_ids)

    # Tests for student_view rendering
    @patch('games.handlers.flashcards.read_resource')
    def test_student_view_renders_fragment(self, mock_read_resource):
        """Test student view returns a fragment with cards."""
        mock_read_resource.return_value = '<div>{{ title }}</div>'

        frag = FlashcardsHandlers.student_view(self.xblock)

        self.assertIsNotNone(frag)
        self.assertIn(self.title, frag.content)

    @patch('games.handlers.flashcards.read_resource')
    def test_student_view_with_no_cards(self, mock_read_resource):
        """Test student view with no cards."""
        mock_read_resource.return_value = '<div>{{ list_length }}</div>'
        self.xblock.cards = []

        frag = FlashcardsHandlers.student_view(self.xblock)

        self.assertIsNotNone(frag)
        self.assertIn('0', frag.content)

    @patch('games.handlers.flashcards.read_resource')
    def test_student_view_with_shuffled_cards(self, mock_read_resource):
        """Test student view with shuffled cards."""
        mock_read_resource.return_value = '<div>{{ list_length }}</div>'
        self.xblock.is_shuffled = True

        frag = FlashcardsHandlers.student_view(self.xblock)

        self.assertIsNotNone(frag)
        self.assertIn('2', frag.content)

    @patch('games.handlers.flashcards.read_resource')
    def test_student_view_reads_the_primary_deck_over_a_stale_cards_mirror(self, mock_read_resource):
        """Learners and Studio must agree when decks and cards storage drift."""
        mock_read_resource.return_value = '<div>{{ list_length }}</div>'
        self.xblock.decks = [{'deck_key': 'deck-1-key', 'name': 'Deck 1', 'cards': [
            {CARD_FIELD.CARD_KEY: 'k1', CARD_FIELD.TERM: 'a', CARD_FIELD.DEFINITION: 'b'},
            {CARD_FIELD.CARD_KEY: 'k2', CARD_FIELD.TERM: 'c', CARD_FIELD.DEFINITION: 'd'},
        ]}]
        self.xblock.cards = []

        frag = FlashcardsHandlers.student_view(self.xblock)

        self.assertIn('2', frag.content)


class TestFlashcardsAutoscrollRegression(TestCase):
    """LP-859: flashcards must not auto-focus the start button on load,
    which scrolled the unit page down to the flashcards."""

    def _read_js(self):
        return read_resource("static/js/src/flashcards.js")

    def test_no_onload_start_button_focus(self):
        """The init setTimeout must not call $startButton.focus() (LP-859)."""
        js = self._read_js()
        self.assertNotIn("$startButton.focus()", js)

    def test_onload_announcement_retained(self):
        """Screen-reader announcement on load must remain."""
        js = self._read_js()
        self.assertIn("Flashcard game. Press Start to begin.", js)