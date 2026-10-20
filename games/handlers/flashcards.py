"""
Flashcards game handler methods.
"""

import random
import base64
import json
import string

from django.template import Context, Template
from web_fragments.fragment import Fragment

from ..constants import CARD_FIELD, CONFIG, DEFAULT
from ..utils import read_resource
from .common import CommonHandlers


class FlashcardsHandlers:
    """Handlers specific to the flashcards game."""

    @staticmethod
    def student_view(xblock, context=None):
        """
        The student view for flashcards game.
        """
        # Same primary-deck derivation as get_settings, so Studio and learners
        # never disagree when the cards mirror drifts from the decks.
        cards = CommonHandlers.primary_cards(CommonHandlers.get_decks(xblock))
        list_length = len(cards)

        if xblock.is_shuffled and cards:
            random.shuffle(cards)

        # Build payload with salt for light obfuscation (pattern similar to matching)
        salt = "".join(random.choices(string.ascii_letters + string.digits, k=CONFIG.SALT_LENGTH))
        payload_cards = []
        for card in cards:
            term_image_alt = card.get(CARD_FIELD.TERM_IMAGE_ALT, "").strip()
            if not term_image_alt:
                term_image_alt = card.get(CARD_FIELD.TERM, "")

            definition_image_alt = card.get(CARD_FIELD.DEFINITION_IMAGE_ALT, "").strip()
            if not definition_image_alt:
                definition_image_alt = card.get(CARD_FIELD.DEFINITION, "")

            payload_cards.append(
                {
                    "id": card.get(CARD_FIELD.CARD_KEY, ""),
                    "term": card.get(CARD_FIELD.TERM, ""),
                    "definition": card.get(CARD_FIELD.DEFINITION, ""),
                    "term_image": card.get(CARD_FIELD.TERM_IMAGE, ""),
                    "definition_image": card.get(CARD_FIELD.DEFINITION_IMAGE, ""),
                    "term_image_alt": term_image_alt,
                    "definition_image_alt": definition_image_alt,
                }
            )
        mapping_payload = {"cards": payload_cards, "salt": salt}
        encoded_mapping = base64.b64encode(json.dumps(mapping_payload).encode()).decode()

        # Random variable names for light obfuscation
        var_names = CommonHandlers.generate_unique_var_names(
            ["runtime", "elem", "tag", "payload", "err"], min_len=3, max_len=6
        )

        # Unique id for embedded data element (script tag)
        data_element_id = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=16)
        )

        # Generate unique function name per XBlock to avoid conflicts
        init_function_name = "FlashcardsInit_" + "".join(
            random.choices(string.ascii_lowercase + string.digits, k=8)
        )

        # Obfuscated decoder with unique function name
        obf_decoder = (
            f"function {init_function_name}({var_names['runtime']},{var_names['elem']}){{"
            f"try{{"
            f"var {var_names['tag']}=$('#{data_element_id}',{var_names['elem']});"
            f"if(!{var_names['tag']}.length){{console.error('Flashcards: Data element not found');return;}}"
            f"var {var_names['payload']}=JSON.parse(atob({var_names['tag']}.text()));"
            f"{var_names['tag']}.remove();"
            f"if({var_names['payload']}&&{var_names['payload']}.cards){{"
            f"if(typeof GamesXBlockFlashcardsInit==='function'){{"
            f"GamesXBlockFlashcardsInit({var_names['runtime']},{var_names['elem']},{var_names['payload']}.cards);"
            f"}}else{{console.error('Flashcards: GamesXBlockFlashcardsInit not defined');}}"
            f"}}else{{console.error('Flashcards: Invalid payload');}}"
            f"}}catch({var_names['err']}){{console.error('Flashcards decode failed:',{var_names['err']});}}}}"
        )

        template_context = {
            "title": getattr(xblock, "title", DEFAULT.FLASHCARDS_TITLE),
            "list_length": list_length,
            "encoded_mapping": encoded_mapping,
            "obf_decoder": obf_decoder,
            "data_element_id": data_element_id,
        }

        template_str = read_resource("static/html/flashcards.html")
        template = Template(template_str)
        html = template.render(Context(template_context))

        frag = Fragment(html)
        frag.add_css(
            read_resource("static/css/flashcards.css")
        )
        frag.add_javascript(
            read_resource("static/js/src/flashcards.js")
        )
        frag.add_javascript(obf_decoder)
        frag.initialize_js(init_function_name)
        return frag
