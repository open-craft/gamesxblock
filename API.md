# Games XBlock API Documentation

This document describes the APIs available in the Games XBlock for implementing gamification features in Open edX courses. The XBlock supports two game types: **Flashcards** and **Matching**.

## Table of Contents

- [XBlock Fields](#xblock-fields)
- [Common APIs](#common-apis)
- [Flashcards Game APIs](#flashcards-game-apis)
- [Matching Game APIs](#matching-game-apis)
- [Data Structures](#data-structures)

---

## XBlock Fields

The Games XBlock uses the following fields to store configuration and state:

### Content-Scoped Fields
- **`title`** (string): The title displayed in the XBlock. Default varies by game type.
- **`decks`** (list): Ordered list of deck objects. The **first deck is the primary deck**: it is the deck older clients call `cards` and the deck learners render today. A block authored before decks existed has no stored `decks` and is presented as one deck named `Deck 1` without being rewritten. Decks are stored in XBlock fields, so ordinary OLX serialization preserves them; there is no separate import/export module.
- **`cards`** (list): Compatibility view of the primary deck, kept in step by `save_settings` (`cards == decks[0].cards`, `list_length == len(cards)`). It is derived, never a second source of truth. Older clients keep reading and writing this field.
- **`list_length`** (integer): Stored count of the cards in the primary deck, tracked through the `cards` mirror.

### Settings-Scoped Fields
- **`display_name`** (string): Display name for the XBlock. Default: `"Games"`.
- **`game_type`** (string): Type of game - either `"flashcards"` or `"matching"`. Default: `"flashcards"`.
- **`is_shuffled`** (boolean): Whether cards should be shuffled. Default: `true`.
- **`has_timer`** (boolean): Whether the game should display a timer. Default: `true`.

### User State Fields
- **`best_time`** (integer): Best completion time in seconds for matching game (user-specific). This is the only user state field.

### Study progress is not stored by the XBlock
Learner study progress (selected deck, Got it/Missed it queue, completion, reset) is owned by the browser `localStorage` and keyed per learner, block and deck. It is **not** accepted by `get_settings` or `save_settings`, not stored in any XBlock field or `user_state`, not graded, and not synced across devices or browsers. These handlers carry authored configuration only; adding progress fields or handlers here is out of contract.

### OLX compatibility
A block with stored decks exports `decks` and the `cards` mirror together, and an import restores both; a legacy cards-only block exports only `cards`. A block exported with multiple decks and imported into a deployment running an older Games XBlock loses the `decks` attribute (the older code ignores the unknown attribute with a `does not contain field decks` warning) while the `cards` mirror still loads the primary deck, so the content degrades to one deck instead of failing. That is why `cards` must always stay in step with the primary deck.

---

## Common APIs

These APIs work across both flashcards and matching game types.

### `get_settings`

**Type**: JSON Handler
**Description**: Retrieves authored configuration only: game type, decks, the primary deck's cards, shuffle setting, and timer setting. No learner study progress is returned.

**Request**:
```json
{}
```

**Response**:
```json
{
  "game_type": "flashcards",
  "decks": [
    {
      "deck_key": "9f1c2f7e-6a4b-4f3c-8f1e-2b7d5c9a0e11",
      "name": "Deck 1",
      "cards": [
        {
          "term": "Python",
          "term_image": "http://example.com/python.png",
          "definition": "A high-level programming language",
          "definition_image": "",
          "order": 0,
          "card_key": "550e8400-e29b-41d4-a716-446655440000"
        }
      ]
    }
  ],
  "cards": [
    {
      "term": "Python",
      "term_image": "http://example.com/python.png",
      "definition": "A high-level programming language",
      "definition_image": "",
      "order": 0,
      "card_key": "550e8400-e29b-41d4-a716-446655440000"
    }
  ],
  "is_shuffled": true,
  "has_timer": true
}
```

**Fields**:
- `game_type` (string): Current game type (`"flashcards"` or `"matching"`)
- `decks` (array): Ordered list of deck objects (see [Deck Object](#deck-object)). Always present and never empty; a legacy `cards`-only block appears as one deck named `Deck 1`. The first entry is the primary deck.
- `cards` (array): Compatibility view of the primary deck, identical to `decks[0].cards` (see [Card Object](#card-object)). Read it when you only understand the older single-deck shape; it is derived, never independently authoritative.
- `is_shuffled` (boolean): Shuffle setting
- `has_timer` (boolean): Timer setting

---

### `save_settings`

**Type**: JSON Handler
**Description**: Saves game type, settings, and authored content in one call. It is a PATCH for top-level fields: a field left out of the payload keeps its current value. Authored content is replaced only when `decks` or `cards` is sent, and `decks` wins if both are. Study progress is never accepted here (see [Study progress is not stored by the XBlock](#study-progress-is-not-stored-by-the-xblock)).

**Request**:
```json
{
  "game_type": "flashcards",
  "is_shuffled": true,
  "has_timer": false,
  "display_name": "My Vocabulary Game",
  "decks": [
    {
      "deck_key": "9f1c2f7e-6a4b-4f3c-8f1e-2b7d5c9a0e11",
      "name": "Deck 1",
      "cards": [
        {
          "term": "Algorithm",
          "term_image": "",
          "definition": "A step-by-step procedure for solving a problem",
          "definition_image": "http://example.com/algo.png"
        }
      ]
    },
    {
      "deck_key": "3b6d8e2a-1c4f-4a7d-9e0b-5f2c8d6a1b33",
      "name": "Deck 2",
      "cards": [
        {
          "term": "Data Structure",
          "term_image": "http://example.com/ds.png",
          "definition": "A way of organizing data efficiently",
          "definition_image": ""
        }
      ]
    }
  ]
}
```

**Response** (Success):
```json
{
  "success": true,
  "game_type": "flashcards",
  "decks": [
    {
      "deck_key": "9f1c2f7e-6a4b-4f3c-8f1e-2b7d5c9a0e11",
      "name": "Deck 1",
      "cards": [
        {
          "term": "Algorithm",
          "term_image": "",
          "definition": "A step-by-step procedure for solving a problem",
          "definition_image": "http://example.com/algo.png",
          "order": 0,
          "card_key": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
        }
      ]
    },
    {
      "deck_key": "3b6d8e2a-1c4f-4a7d-9e0b-5f2c8d6a1b33",
      "name": "Deck 2",
      "cards": [
        {
          "term": "Data Structure",
          "term_image": "http://example.com/ds.png",
          "definition": "A way of organizing data efficiently",
          "definition_image": "",
          "order": 0,
          "card_key": "3f847e5d-8a6b-4c3e-9d2a-1b8f7c4e0d9a"
        }
      ]
    }
  ],
  "cards": [
    {
      "term": "Algorithm",
      "term_image": "",
      "definition": "A step-by-step procedure for solving a problem",
      "definition_image": "http://example.com/algo.png",
      "order": 0,
      "card_key": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
    }
  ],
  "count": 1,
  "is_shuffled": true,
  "has_timer": false
}
```

**Response** (Error):
```json
{
  "success": false,
  "error": "Each card must have term and definition"
}
```

**Validation Rules**:
- Omitted `game_type`, `is_shuffled`, `has_timer` and `display_name` keep their current values. A `null` or non-string `display_name` also keeps the current name; it never resets the block title.
- Sending `game_type` rewrites the internal `title` to that type's default (`Flashcards` or `Matching`), even when the type is unchanged; omitting `game_type` leaves `title` alone.
- A corrupt stored value cannot be repaired by omission: if the stored `game_type` is not a valid type, or a stored `is_shuffled`/`has_timer` is not a boolean, the save is rejected until the caller sends a valid replacement.
- An explicit invalid `game_type`, or an explicit `is_shuffled`/`has_timer` that is not a boolean, rejects the save and writes nothing.
- `decks` must be an ordered list with at least one deck; an empty `decks` list is rejected.
- Each deck must be an object with a non-empty `name` and a `cards` list. Every submitted deck must include `cards`; `"cards": []` is the valid empty deck.
- Deck names are trimmed before saving and must be unique ignoring case.
- Missing `deck_key` and `card_key` values are assigned on save; existing keys are preserved.
- A card belongs to exactly one deck. Its `card_key` is preserved when it moves between decks.
- Each card must be an object containing both `term` and `definition` fields.
- Empty decks are allowed.
- Deck and card shapes are closed: only the fields listed in [Deck Object](#deck-object) and [Card Object](#card-object) are stored, and unknown keys are dropped.
- Array position is authoritative: whenever deck or card content is written, `order` is set to the card's zero-based index inside its deck.
- Invalid deck or card data rejects the whole save; stored content is unchanged.
- A `decks` payload is the complete list: it replaces every stored deck, so decks left out of the payload are deleted with their cards.
- A `cards`-only payload updates the primary deck and preserves every other deck's cards, keys and names; each preserved deck is validated and canonicalized before the save, so its `order` values are renumbered to their array indexes. A preserved deck that is itself invalid (missing `cards`, a blank or duplicate name, a duplicate key) rejects the whole save and writes nothing.
- A payload with neither `decks` nor `cards` leaves authored content alone; a block that already has stored decks still gets its `cards`/`list_length` mirror resynced to the primary deck.
- `cards` always mirrors the primary deck after a save, and `list_length` equals its card count.
- The response `count` is the number of cards in the primary deck (the `cards` mirror), not the total across decks.

**Legacy cards-only saves**:

```json
{
  "game_type": "flashcards",
  "cards": [
    {
      "term": "Algorithm",
      "definition": "A step-by-step procedure for solving a problem"
    }
  ]
}
```

A payload without `decks` updates the primary deck only. Every other deck keeps its identity, its cards and their array positions; its card fields and `order` values are canonicalized.

**Compatibility recommendation**: clients that understand decks should read and write `decks` and treat `cards` as a read-only mirror. Clients that only understand the older shape must keep sending `cards`: that save updates the primary deck and leaves the other decks alone, so multi-deck content survives old-client saves. Never treat `cards` and `decks` as two independent sources of truth.

---

### `upload_image`

**Type**: HTTP Handler
**Description**: Uploads an image file to configured storage (S3 or default) and returns the URL.

**Request**:
- **Method**: POST
- **Content-Type**: multipart/form-data
- **Parameters**:
  - `file` (file): The image file to upload

**Supported Extensions**: jpg, jpeg, png, gif, webp, svg

**Response** (Success):
```json
{
  "success": true,
  "url": "https://s3.amazonaws.com/bucket/games/block_id/abc123def456.png",
  "filename": "my-image.png",
  "file_path": "games/block_id/abc123def456.png"
}
```

**Response** (Error - No Extension):
```json
{
  "success": false,
  "error": "File must have an extension"
}
```

**Response** (Error - Invalid Extension):
```json
{
  "success": false,
  "error": "Unsupported file type '.bmp'. Allowed: gif, jpg, jpeg, png, svg, webp"
}
```

**Notes**:
- File is stored with MD5 hash to prevent duplicates
- File path format: `gamesxblock/<block_id>/<md5_hash>.<ext>`

---

### `delete_image_handler`

**Type**: JSON Handler
**Description**: Deletes an image from storage by its key/path.

**Request**:
```json
{
  "key": "gamesxblock/block_id/abc123def456.png"
}
```

**Response** (Success):
```json
{
  "success": true,
  "key": "gamesxblock/block_id/abc123def456.png"
}
```

**Response** (Error - Missing Key):
```json
{
  "success": false,
  "error": "Missing key"
}
```

**Response** (Error - File Not Found):
```json
{
  "success": false,
  "key": "gamesxblock/block_id/nonexistent.png"
}
```

---

## Flashcards Game APIs

### `student_view` (Flashcards)

**Type**: XBlock View
**Description**: Renders the flashcards game interface for students.

**Features**:
- Displays cards one at a time
- Flip animation to reveal definitions
- Navigate forward/backward through cards
- Optional shuffle on load
- Progress indicator

**Rendered Context**:
```python
{
  "title": "Flashcards",
  "list_length": 10,
  "encoded_mapping": "eyJjYXJkcyI6W3sidGVybSI6...",  # Base64-encoded card data
  "obf_decoder": "function FlashcardsInit(r,e){...}",  # Obfuscated initialization
  "data_element_id": "abc123xyz789"
}
```

**Data Payload Structure** (decoded from `encoded_mapping`):
```json
{
  "cards": [
    {
      "id": "card-uuid",
      "term": "Front text",
      "definition": "Back text",
      "term_image": "http://example.com/front.png",
      "definition_image": "http://example.com/back.png"
    }
  ],
  "salt": "randomString123"
}
```

---

## Matching Game APIs

### `student_view` (Matching)

**Type**: XBlock View
**Description**: Renders the matching game interface for students where they match terms with definitions.

**Features**:
- Two-column layout (terms on left, definitions on right)
- Click to match pairs
- Optional timer to track completion time
- Multi-page support for large card sets (6 matches per page by default)
- Confetti animation on completion
- Best time tracking

**Rendered Context**:
```python
{
  "title": "Matching Game",
  "list_length": 12,
  "all_pages": [
    {
      "left_items": [{"text": "Python", "index": 0}, ...],
      "right_items": [{"text": "Programming language", "index": 1}, ...]
    }
  ],
  "has_timer": true,
  "total_pages": 2,
  "encoded_mapping": "eyJrZXkiOiJnQUFBQUFBQUFBQUE...",
  "obf_decoder": "function MatchingInit(r,e){...}",
  "data_element_id": "xyz789abc123"
}
```

**Data Payload Structure** (decoded from `encoded_mapping`):
```json
{
  "key": "gAAAAABh...encrypted_mapping_data",
  "pages": [
    {
      "left_items": [
        {"text": "Python", "index": 0},
        {"text": "JavaScript", "index": 2}
      ],
      "right_items": [
        {"text": "Programming language", "index": 1},
        {"text": "Web scripting", "index": 3}
      ]
    }
  ]
}
```

**Security Note**: The matching key mapping is encrypted using Fernet symmetric encryption with a key derived from the block ID and a salt.

---

### `start_matching_game`

**Type**: JSON Handler
**Description**: Decrypts and returns the key mapping for matching game validation. Called when game starts to enable client-side match validation.

**Request**:
```json
{
  "matching_key": "gAAAAABh3k2J..."
}
```

**Response** (Success):
```json
{
  "success": true,
  "data": [
    "550e8400-e29b-41d4-a716-446655440001",
    "3f847e5d-8a6b-4c3e-9d2a-1b8f7c4e0d02",
    null,
    null
  ]
}
```

**Response** (Error - Missing Key):
```json
{
  "success": false,
  "error": "Missing matching_key parameter"
}
```

**Response** (Error - Decryption Failed):
```json
{
  "success": false,
  "error": "Failed to decrypt mapping: Invalid token"
}
```

**Notes**:
- The `data` array contains UUID-like strings representing valid matches
- Each index maps to its matching pair's index
- Encryption prevents students from easily discovering correct matches

---

### `complete_matching_game`

**Type**: JSON Handler
**Description**: Records completion time and updates the user's best time if the new time is better.

**Request**:
```json
{
  "new_time": 45
}
```

**Response**:
```json
{
  "new_time": 45,
  "prev_best_time": 52
}
```

**Response** (First Completion):
```json
{
  "new_time": 67,
  "prev_best_time": null
}
```

**Fields**:
- `new_time` (integer): Completion time in seconds for this attempt
- `prev_best_time` (integer|null): Previous best time, or `null` if first completion

**Behavior**:
- If `new_time < prev_best_time`, updates `best_time` field
- If `prev_best_time` is `null`, sets `best_time` to `new_time`

---

### `refresh_game`

**Type**: HTTP Handler
**Description**: Re-renders the matching game view with newly shuffled cards (if shuffle is enabled).

**Request**:
- **Method**: GET or POST
- **Parameters**: None

**Response**:
- **Content-Type**: text/html; charset=UTF-8
- **Body**: Full HTML fragment of the matching game with new shuffle

**Use Case**: Called when student wants to retry the game with different arrangement.

---

## Data Structures

### Deck Object

Represents one named deck in a Flashcards block.

```json
{
  "deck_key": "9f1c2f7e-6a4b-4f3c-8f1e-2b7d5c9a0e11",
  "name": "Deck 1",
  "cards": [
    {
      "term": "Algorithm",
      "definition": "A step-by-step procedure for solving a problem",
      "card_key": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
    }
  ]
}
```

**Fields**:
- **`deck_key`** (string, optional): Stable deck identifier. Assigned on save when missing.
- **`name`** (string, required): Deck name. Trimmed on save and unique ignoring case.
- **`cards`** (array, required): Ordered list of card objects (see [Card Object](#card-object)). Every submitted deck must include `cards`; `[]` is the valid empty deck.

Decks are ordered; array position is authoritative and is the order editors and learners see. The first deck is the primary deck: `get_settings.cards` and the learner views use it, and the `cards` field mirrors it. Deck authoring applies to Flashcards only; Matching preserves stored decks but does not use them. Every deck is validated on save and any invalid deck rejects the whole save.

---

### Card Object

Represents a single term-definition pair in the game.

```json
{
  "term": "Algorithm",
  "term_image": "http://example.com/algo.png",
  "definition": "A step-by-step procedure for solving a problem",
  "definition_image": "http://example.com/algo-diagram.png",
  "order": 0,
  "card_key": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
}
```

**Fields**:
- **`term`** (string, required): The term/question/front side text
- **`term_image`** (string, optional): URL to image for the term
- **`definition`** (string, required): The definition/answer/back side text
- **`definition_image`** (string, optional): URL to image for the definition
- **`order`** (integer): Display position. Always set on save to the card's zero-based index in its deck; a value sent by the client is ignored because array order is authoritative.
- **`card_key`** (string, optional): Stable card identifier, preserved when the card moves between decks (auto-generated as UUID if missing)

---

### Item Object (Matching Game)

Represents a draggable/clickable item in the matching game interface.

```json
{
  "text": "Python",
  "index": 0
}
```

**Fields**:
- **`text`** (string): Display text for the item
- **`index`** (integer): Unique index used for match validation

---

### Page Object (Matching Game)

Represents one page of matches in a multi-page matching game.

```json
{
  "left_items": [
    {"text": "Python", "index": 0},
    {"text": "JavaScript", "index": 2}
  ],
  "right_items": [
    {"text": "Programming language", "index": 1},
    {"text": "Web scripting", "index": 3}
  ]
}
```

**Fields**:
- **`left_items`** (array): List of item objects for the left column (terms)
- **`right_items`** (array): List of item objects for the right column (definitions)

**Configuration**: Default is 6 matches per page (configurable via `CONFIG.MATCHES_PER_PAGE`).

---

## Error Handling

All JSON handlers report validation failures with **HTTP 200** and `"success": false`; they are not HTTP 4xx responses. Treat `success` as the result flag and `error` as the message to show. A rejected save writes nothing, so the stored block is unchanged.

```json
{
  "success": false,
  "error": "Error message describing what went wrong"
}
```

Common error scenarios:
- Missing required parameters
- Invalid data format
- Encryption/decryption failures
- File upload issues (invalid extension, file too large, etc.)
- Storage backend errors

---

## Security Features

### Encryption
- Matching game uses Fernet symmetric encryption for key mapping
- Encryption key derived from block ID and salt (consistent across requests)
- Prevents students from easily discovering correct matches

### Obfuscation
- JavaScript initialization functions use randomized variable names
- Data embedded in DOM with random element IDs
- Payload encoded in Base64 before embedding
- Makes it harder to reverse-engineer game logic

### Validation
- Server-side validation of deck and card structure; invalid saves are rejected atomically
- File extension whitelist for uploads
- MD5 hashing prevents duplicate uploads
- Storage key validation before deletion

---

## Configuration Constants

Key configuration values (from `games/constants.py`):

- **`MATCHES_PER_PAGE`**: 6 - Number of term-definition pairs per page in matching game
- **`RANDOM_STRING_LENGTH`**: 16 - Length of random keys for obfuscation
- **`SALT_LENGTH`**: 12 - Length of salt for payload obfuscation
- **`ENCRYPTION_SALT`**: Internal salt for key generation
- **`PATH_PREFIX`**: "gamesxblock" - Prefix for uploaded file paths

---

## Usage Examples

### Example 1: Create a Flashcards Game

```python
# 1. Save settings with flashcards type
response = xblock.save_settings({
    "game_type": "flashcards",
    "is_shuffled": true,
    "has_timer": false,
    "display_name": "Spanish Vocabulary",
    "decks": [
        {
            "name": "Deck 1",
            "cards": [
                {"term": "Hola", "definition": "Hello"},
                {"term": "Adiós", "definition": "Goodbye"}
            ]
        },
        {
            "name": "Deck 2",
            "cards": [
                {"term": "Gracias", "definition": "Thank you"}
            ]
        }
    ]
})

# `cards` is rebuilt as the Deck 1 mirror.

# 2. Upload images for cards (if needed)
# POST to upload_image handler with multipart/form-data

# 3. Students view the flashcards via student_view
# They can flip cards, navigate, and study terms
```

### Example 2: Create a Matching Game with Timer

```python
# 1. Save settings with matching type
response = xblock.save_settings({
    "game_type": "matching",
    "is_shuffled": true,
    "has_timer": true,
    "display_name": "Computer Science Terms",
    "cards": [
        {
            "term": "Algorithm",
            "definition": "Step-by-step procedure"
        },
        {
            "term": "Variable",
            "definition": "Named storage location"
        },
        {
            "term": "Loop",
            "definition": "Repeated execution"
        }
    ]
})

# 2. Students play the matching game
# - Game loads encrypted key mapping
# - Timer starts when first match is made
# - On completion, time is submitted to complete_matching_game
# - Best time is tracked per user
```

### Example 3: Upload and Use Images

```javascript
// Frontend: Upload image file
const formData = new FormData();
formData.append('file', imageFile);

fetch(uploadImageUrl, {
    method: 'POST',
    body: formData
}).then(response => response.json())
  .then(data => {
      if (data.success) {
          // Use data.url in card definition
          const card = {
              term: "Python Logo",
              term_image: data.url,
              definition: "High-level programming language",
              definition_image: ""
          };
      }
  });
```

---

## Internationalization (i18n)

The Games XBlock supports multiple languages:

- **Default**: English (en)
- **Supported**: Spanish (es_419)
- All user-facing strings are translatable using Django's translation framework
- Use `gettext()` or `gettext_lazy()` for runtime translation
- Translation files located in `games/locale/`
