"""
Tests for flashcards and matching handlers.
"""
from unittest.mock import Mock, patch
from django.test import TestCase
from faker import Faker
from xblock.field_data import DictFieldData
from xblock.fields import ScopeIds

from games.games import GamesXBlock
from games.handlers.matching import MatchingHandlers
from games.constants import GAME_TYPE, CARD_FIELD


class TestMatchingHandlers(TestCase):
    """Tests for matching handler methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.fake = Faker()
        self.runtime = Mock()
        usage_id = Mock()
        usage_id.block_id = self.fake.uuid4()
        self.scope_ids = ScopeIds(self.fake.uuid4(), "games", self.fake.uuid4(), usage_id)
        self.title = self.fake.catch_phrase()
        self.field_data = DictFieldData({
            'game_type': GAME_TYPE.MATCHING,
            'cards': [
                {CARD_FIELD.TERM: self.fake.word(), CARD_FIELD.DEFINITION: self.fake.sentence()},
                {CARD_FIELD.TERM: self.fake.word(), CARD_FIELD.DEFINITION: self.fake.sentence()},
            ],
            'is_shuffled': self.fake.boolean(),
            'has_timer': self.fake.boolean(),
            'title': self.title,
            'best_time': None,
        })
        self.xblock = GamesXBlock(self.runtime, self.field_data, self.scope_ids)

    # Tests for student_view rendering
    @patch('games.handlers.matching.read_resource')
    def test_student_view_renders_fragment(self, mock_read_resource):
        """Test student view returns a fragment."""
        mock_read_resource.return_value = '<div>{{ title }}</div>'

        frag = MatchingHandlers.student_view(self.xblock)

        self.assertIsNotNone(frag)
        self.assertIn(self.title, frag.content)

    @patch('games.handlers.matching.read_resource')
    def test_student_view_with_shuffled_cards(self, mock_read_resource):
        """Test student view with shuffled cards."""
        mock_read_resource.return_value = '<div>{{ list_length }}</div>'
        self.xblock.is_shuffled = True

        frag = MatchingHandlers.student_view(self.xblock)

        self.assertIsNotNone(frag)
        self.assertIn('2', frag.content)

    @patch('games.handlers.matching.read_resource')
    def test_student_view_reads_the_primary_deck_over_a_stale_cards_mirror(self, mock_read_resource):
        """Learners and Studio must agree when decks and cards storage drift."""
        mock_read_resource.return_value = '<div>{{ list_length }}</div>'
        self.xblock.decks = [{'deck_key': 'deck-1-key', 'name': 'Deck 1', 'cards': [
            {CARD_FIELD.CARD_KEY: 'k1', CARD_FIELD.TERM: 'a', CARD_FIELD.DEFINITION: 'b'},
            {CARD_FIELD.CARD_KEY: 'k2', CARD_FIELD.TERM: 'c', CARD_FIELD.DEFINITION: 'd'},
        ]}]
        self.xblock.cards = []

        frag = MatchingHandlers.student_view(self.xblock)

        self.assertIn('2', frag.content)

    @patch('games.handlers.matching.read_resource')
    def test_student_view_with_multiple_pages(self, mock_read_resource):
        """Test student view with multiple pages of cards."""
        mock_read_resource.return_value = '<div>{{ total_pages }}</div>'
        # Add enough cards to create multiple pages (6 cards per page by default)
        cards = []
        for _ in range(15):
            cards.append({
                CARD_FIELD.TERM: self.fake.word(),
                CARD_FIELD.DEFINITION: self.fake.sentence()
                })
        self.xblock.cards = cards

        frag = MatchingHandlers.student_view(self.xblock)

        self.assertIsNotNone(frag)

    # Tests for refresh_game
    @patch.object(MatchingHandlers, 'student_view')
    def test_refresh_game(self, mock_student_view):
        """Test refresh game handler."""
        mock_frag = Mock()
        refresh_content = f'<div>{self.fake.sentence()}</div>'
        mock_frag.content = refresh_content
        mock_student_view.return_value = mock_frag

        request = Mock()
        response = MatchingHandlers.refresh_game(self.xblock, request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(refresh_content, response.body.decode())
        mock_student_view.assert_called_once()

    # Tests for complete_matching_game
    def test_complete_matching_game_first_time(self):
        """Test completing matching game for the first time."""
        new_time = self.fake.pyfloat(min_value=10.0, max_value=100.0, right_digits=2)
        data = {'new_time': new_time}

        result = MatchingHandlers.complete_matching_game(self.xblock, data)

        self.assertEqual(result['new_time'], new_time)
        self.assertIsNone(result['prev_best_time'])
        self.assertEqual(self.xblock.best_time, new_time)

    def test_complete_matching_game_with_better_time(self):
        """Test completing matching game with a better time."""
        prev_time = self.fake.pyfloat(min_value=50.0, max_value=100.0, right_digits=2)
        new_time = prev_time - self.fake.pyfloat(min_value=5.0, max_value=20.0, right_digits=2)
        self.xblock.best_time = prev_time
        data = {'new_time': new_time}

        result = MatchingHandlers.complete_matching_game(self.xblock, data)

        self.assertEqual(result['new_time'], new_time)
        self.assertEqual(result['prev_best_time'], prev_time)
        self.assertEqual(self.xblock.best_time, new_time)

    def test_complete_matching_game_with_worse_time(self):
        """Test completing matching game with a worse time."""
        prev_time = self.fake.pyfloat(min_value=20.0, max_value=50.0, right_digits=2)
        new_time = prev_time + self.fake.pyfloat(min_value=5.0, max_value=20.0, right_digits=2)
        self.xblock.best_time = prev_time
        data = {'new_time': new_time}

        result = MatchingHandlers.complete_matching_game(self.xblock, data)

        self.assertEqual(result['new_time'], new_time)
        self.assertEqual(result['prev_best_time'], prev_time)
        self.assertEqual(self.xblock.best_time, prev_time)  # Should not update
