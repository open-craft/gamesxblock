"""An XBlock providing gamification capabilities."""

from django.utils.translation import gettext_lazy as _
from xblock.core import XBlock
from xblock.fields import Boolean, Integer, List, Scope, String

from .constants import DEFAULT
from .handlers import CommonHandlers, FlashcardsHandlers, MatchingHandlers


class GamesXBlock(XBlock):
    """
    An XBlock for creating games.

    The Student view will display the game content and allow the student to interact
    accordingly.

    The editor view will allow course authors to create and manipulate the games.
    """

    title = String(
        default=DEFAULT.FLASHCARDS_TITLE,
        scope=Scope.content,
        help=_("The title of the block to be displayed in the xblock."),
    )
    display_name = String(
        default=DEFAULT.DISPLAY_NAME,
        scope=Scope.settings,
        help="Display name for this XBlock",
    )

    # Change default to 'matching' for matching game and 'flashcards' for flashcards game to test
    game_type = String(
        default=DEFAULT.GAME_TYPE,
        scope=Scope.settings,
        help=_(
            "The kind of game this xblock is responsible for ('flashcards' or 'matching' for now)."
        ),
    )

    cards = List(
        default=[], scope=Scope.content, help=_("The list of terms and definitions.")
    )

    decks = List(
        default=[], scope=Scope.content,
        help=_("The ordered decks; each deck has a key, a name and its own cards."),
    )

    list_length = Integer(
        default=len(cards.default),
        scope=Scope.content,
        help=_("A field for the length of the list for convenience."),
    )

    best_time = Integer(
        default=None,
        scope=Scope.user_state,
        help=_("Best time (in seconds) for completing the matching game."),
    )

    is_shuffled = Boolean(
        default=DEFAULT.IS_SHUFFLED,
        scope=Scope.settings,
        help=_("Whether the cards should be shuffled"),
    )

    has_timer = Boolean(
        default=DEFAULT.HAS_TIMER,
        scope=Scope.settings,
        help=_("Whether the game should have a timer"),
    )

    def get_mode(self):
        """Detect if in preview/author mode."""
        if hasattr(self.runtime, 'is_author_mode') and self.runtime.is_author_mode:
            return "preview"
        return "normal"

    def student_view(self, context=None):
        """
        The primary view of the GamesXBlock, shown to students
        when viewing courses. Routes to appropriate handler based on game_type.
        """
        if self.game_type == "flashcards":
            frag = FlashcardsHandlers.student_view(self, context)
        elif self.game_type == "matching":
            frag = MatchingHandlers.student_view(self, context)
        else:
            # Default fallback
            frag = MatchingHandlers.student_view(self, context)

        return frag

    @XBlock.json_handler
    def get_settings(self, data, suffix=""):
        """Get game type, cards, and shuffle setting in one call."""
        return CommonHandlers.get_settings(self, data, suffix)

    @XBlock.handler
    def upload_image(self, request, suffix=""):
        """
        Upload an image file to configured storage (S3 if set) and return URL.
        """
        return CommonHandlers.upload_image(self, request, suffix)

    @XBlock.json_handler
    def delete_image_handler(self, data, suffix=""):
        """
        Delete an image by storage key.
        Expected: { "key": "games/<block_id>/<hash>.ext" }
        """
        return CommonHandlers.delete_image_handler(self, data, suffix)

    @XBlock.json_handler
    def save_settings(self, data, suffix=""):
        """Save game type, shuffle setting, and all cards in one API call."""
        return CommonHandlers.save_settings(self, data, suffix)

    @XBlock.json_handler
    def complete_matching_game(self, data, suffix=""):
        """Complete the matching game and compare the user's time to the best_time field."""
        return MatchingHandlers.complete_matching_game(self, data, suffix)

    @XBlock.handler
    def refresh_game(self, request, suffix=""):
        """Refresh the game view with new shuffled data."""
        return MatchingHandlers.refresh_game(self, request, suffix)

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            (
                "Multiple GamesXBlock",
                """<vertical_demo>
                <games/>
                <games/>
                <games/>
                </vertical_demo>
             """,
            ),
            (
                "games",
                """<games/>
              """,
            ),
        ]
