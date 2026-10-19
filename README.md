# Games XBlock

An XBlock for adding interactive **Flashcards** and **Matching** games to edX courses.

> **Note:** This repository contains the XBlock backend and learner views. Flashcard deck authoring requires the Games Studio editor in an Authoring MFE; Matching is unchanged.

---

## Features

| | |
|---|---|
| 🃏 **Two game types** | Flashcards and Matching |
| 🗂️ **Flashcard decks** | Multiple named decks authored in the Games Studio editor (Flashcards only); the learner view renders Deck 1 |
| 🖼️ **Image support** | JPG, PNG, GIF, WebP, SVG for terms and definitions |
| 🔀 **Card shuffling** | Re-randomized on every page load when enabled |
| ⏱️ **Timer & best time** | Optional timer with per-student personal best (Matching) |
| 📄 **Pagination** | 5 pairs per page for large card sets |
| 🎉 **Confetti** | Animation on matching game completion |
| 🔒 **Encrypted answer keys** | Correct pairs never exposed in page source |
| 💾 **Configurable storage** | Django default storage or S3 |
| 🚩 **Waffle-flag gated** | Enable/disable at runtime without a redeploy |
| 🌐 **i18n support** | English and Latin-American Spanish included |

---

## Game Types

**🃏 Flashcards** — Single-card flip view over the block's Deck 1 cards. Navigate forward/backward through cards with a progress counter. Images supported on both sides. Multiple named decks are authored in the Games Studio editor.

**🔗 Matching** — Two-column click-to-match interface. Paginated (5 pairs/page), optional timer, tracks personal best, confetti on completion.

---

## Requirements

| Dependency | Version |
|------------|---------|
| Python | 3.9+ |
| Django | 2.2+ |
| XBlock | 1.2.0+ |
| web-fragments | 0.3.0+ |
| django-waffle | 5.0.0+ |
| edx-toggles | 5.4.1+ |
| cryptography | 3.4.8+ |

---

## Installation

```bash
pip install edx-games
```

---

## Usage

    1. In **Studio**, go to **Settings → Advanced Settings**.
    2. Add `"games"` to the **Advanced Module List** and click **Save Changes**.
    3. In your unit, click **Add New Component → Advanced → Games**.
    4. Click **Edit**, select a game type, add cards, configure shuffle/timer, and click **Save**. For Flashcards, create or select a deck before adding cards.

---

## Flashcard decks (Studio authoring)

Deck authoring applies to Flashcards only. Matching consumes the Deck 1 mirror; any additional stored decks are preserved but unused by Matching.

- **Create:** Add a deck and give it a name. Names are required, trimmed, and unique ignoring case.
- **Select:** Choose a deck to edit its cards. Deck order is the creation order.
- **Rename:** An empty name or a name that duplicates another deck ignoring case is rejected; the previous name is kept.
- **Delete:** Deleting a non-empty deck asks for confirmation. The last remaining deck cannot be deleted.
- **Move cards:** Move a card to another deck from the editor. The card keeps its `card_key`; the card order the editor submits for the target deck is preserved.
- **Empty decks:** Allowed in authoring (submit `"cards": []`); the current learner view renders only the `cards`/Deck 1 mirror.

### Existing content and old clients

- A block that only has the legacy `cards` field loads as one deck named `Deck 1`.
- `cards` is stored as the Deck 1 mirror, and `list_length` tracks only that mirror.
- A save from an older client that sends only `cards` updates Deck 1 and preserves every other deck's cards, keys, and order.
- Decks are stored in XBlock fields, so normal OLX export and import preserves them. There is no separate import screen or module.

---

## Configuration

### Waffle Flag

| Flag | Default | Description |
|------|---------|-------------|
| `legacy_studio.enable_games_xblock` | `False` | Enables the XBlock in Legacy Studio |

```bash
# Enable
./manage.py waffle_flag legacy_studio.enable_games_xblock --everyone --create
# Disable
./manage.py waffle_flag legacy_studio.enable_games_xblock --deactivate
```

### Storage Backend

By default, images use Django's `default_storage`. Override with `GAMESXBLOCK_STORAGE` in your LMS and CMS settings:

```python
# Filesystem
GAMESXBLOCK_STORAGE = {
    "storage_class": "django.core.files.storage.FileSystemStorage",
    "settings": {"location": "/path/to/media/games", "base_url": "/media/games/"},
}

# S3
GAMESXBLOCK_STORAGE = {
    "storage_class": "storages.backends.s3boto3.S3Boto3Storage",
    "settings": {"bucket_name": "my-bucket", "location": "games", "querystring_auth": True},
}
```

---

## Security

| | |
|---|---|
| 🔐 **Answer-key encryption** | Matching pairs encrypted with Fernet (AES + HMAC), key derived from block ID |
| 🕵️ **JS obfuscation** | Random variable names, element IDs, and function names on every render |
| ✅ **Image uploads** | Extension whitelist; files deduplicated by MD5 hash |

---
