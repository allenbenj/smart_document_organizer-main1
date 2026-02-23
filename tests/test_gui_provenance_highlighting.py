from __future__ import annotations

from gui.tabs.provenance_highlighting import build_highlight_segments


def test_gui_provenance_highlighting_segments_char_level_spans() -> None:
    text = "abcdefghij"
    spans = [{"start_char": 2, "end_char": 5}]

    parts = build_highlight_segments(text, spans)
    assert parts == [
        {"text": "ab", "highlight": False},
        {"text": "cde", "highlight": True},
        {"text": "fghij", "highlight": False},
    ]


def test_gui_provenance_highlighting_merges_overlaps() -> None:
    text = "abcdefghij"
    spans = [{"start_char": 1, "end_char": 4}, {"start_char": 3, "end_char": 7}]

    parts = build_highlight_segments(text, spans)
    assert parts == [
        {"text": "a", "highlight": False},
        {"text": "bcdefg", "highlight": True},
        {"text": "hij", "highlight": False},
    ]
