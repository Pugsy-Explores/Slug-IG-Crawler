from __future__ import annotations

from unittest.mock import patch

from igscraper.chrome import _check_page


def test_check_page_non_blocking_by_default():
    with patch("builtins.print") as mock_print, patch("builtins.input") as mock_input:
        _check_page("https://example.com")

    mock_input.assert_not_called()
    printed = [args[0] for args, _ in mock_print.call_args_list]
    assert any("Suspicious navigation" in msg for msg in printed)
    assert any("Continuing automatically" in msg for msg in printed)


def test_check_page_interactive_when_env_enabled():
    with patch.dict("os.environ", {"IGSCRAPER_INTERACTIVE_GUARD": "1"}, clear=False):
        with patch("builtins.print") as mock_print, patch("builtins.input") as mock_input:
            _check_page("https://example.com")

    mock_input.assert_called_once()
    printed = [args[0] for args, _ in mock_print.call_args_list]
    assert any("Suspicious navigation" in msg for msg in printed)
