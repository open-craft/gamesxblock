"""
Matching game handler methods.

This module contains handlers specific to the matching game type.
"""

import hashlib
import hmac as _hmac
import random
import secrets

from xblock.core import Response
from django.template import Context, Template
from web_fragments.fragment import Fragment
from ..constants import CONFIG, DEFAULT
from ..utils import read_resource
from .common import CommonHandlers


class MatchingHandlers:
    """Handlers specific to the matching game type."""

    @staticmethod
    def _hmac_hex(key: str, text: str) -> str:
        """Return HMAC-SHA256 hex digest of text using key."""
        return _hmac.new(key.encode(), text.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def student_view(xblock, context=None):
        """Render the student view for the matching game."""
        # Same primary-deck derivation as get_settings, so Studio and learners
        # never disagree when the cards mirror drifts from the decks.
        cards = CommonHandlers.primary_cards(CommonHandlers.get_decks(xblock))
        list_length = len(cards)
        session_key = secrets.token_hex(32)

        matches_per_page = CONFIG.MATCHES_PER_PAGE
        pages = []
        for i in range(0, len(cards), matches_per_page):
            page_cards = cards[i:i + matches_per_page]
            left_items = []
            right_items = []
            for card in page_cards:
                def_text = card.get("definition", "")
                def_hash = MatchingHandlers._hmac_hex(session_key, def_text)
                left_items.append({
                    "text": card.get("term", ""),
                    "match": def_hash,
                })
                right_items.append({"text": def_text, "hash": def_hash})
            if xblock.is_shuffled:
                random.shuffle(left_items)
                random.shuffle(right_items)
            pages.append({"left_items": left_items, "right_items": right_items})

        total_pages = len(pages)

        template_context = {
            "title": getattr(xblock, "title", DEFAULT.MATCHING_TITLE),
            "list_length": list_length,
            "all_pages": pages,
            "has_timer": getattr(xblock, "has_timer", DEFAULT.HAS_TIMER),
            "total_pages": total_pages,
            "pages_json": pages,
            "block_id": xblock.scope_ids.usage_id.block_id,
        }

        template_str = read_resource("static/html/matching.html")
        template = Template(template_str)
        html = template.render(Context(template_context))

        frag = Fragment(html)
        frag.add_css(
            read_resource("static/css/matching.css")
        )
        frag.add_css(
            read_resource("static/css/confetti.css")
        )
        frag.add_javascript(
            read_resource("static/js/src/matching.js")
        )
        frag.add_javascript(
            read_resource("static/js/src/confetti.js")
        )
        frag.initialize_js('GamesXBlockMatchingInit')
        return frag

    @staticmethod
    def refresh_game(xblock, request, suffix=""):
        """Refresh the game view with new shuffled data."""
        frag = MatchingHandlers.student_view(xblock, context=None)

        return Response(frag.content, content_type="text/html", charset="UTF-8")

    @staticmethod
    def complete_matching_game(xblock, data, suffix=""):
        """Complete the matching game and compare the user's time to the best_time field."""
        new_time = data["new_time"]
        prev_best_time = xblock.best_time

        if prev_best_time is None or new_time < prev_best_time:
            xblock.best_time = new_time

        return {
            "new_time": new_time,
            "prev_best_time": prev_best_time,
        }
