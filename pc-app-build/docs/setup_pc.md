# PC Setup Guide

## Start Notes API

```bat
scripts\start_notes_api.bat
```

## Seed Product Demo Data

For demo-only databases:

```bat
python scripts\seed_demo_data.py --reset
```

To keep existing notes and only replace old development demo notes:

```bat
python scripts\replace_demo_notes.py
```

## Start PC App

```bat
scripts\start_pc_app.bat
```

## Verification

```text
1. Voice assistant floating button has no bottom-right overlap artifact.
2. Notes display GMT+8 time.
3. Note lists show scrollbars when there are many notes.
4. Note list scrolling stops at the bounds without strong bounce.
5. Notes use multiple card colors.
6. Search updates while typing and resets to all notes when cleared.
7. Multi-select is available on normal note lists and search results.
8. Selected notes can be deleted together.
9. Selected notes can be pinned together.
10. Deleted notes can be restored.
11. Deleted notes can be permanently deleted after confirmation.
```
