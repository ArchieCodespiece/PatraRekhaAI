import pytest
from services.romanized_normalizer import (
    normalize_romanized_query,
)


class TestNormalizeRomanized:
    """Test the normalize_romanized_query() function."""

    def test_hinglish_basic(self):
        result = normalize_romanized_query(
            "Mujhe AI model ki zaroorat hai"
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_english_passthrough(self):
        text = "This is a standard English sentence."
        result = normalize_romanized_query(text)
        assert result == text

    def test_benglish(self):
        result = normalize_romanized_query(
            "Eta ek sample document je AI somporkito."
        )
        assert isinstance(result, str)

    def test_tanglish(self):
        result = normalize_romanized_query(
            "Idhu oru sample document AI pathi."
        )
        assert isinstance(result, str)

    def test_hindi_script_passthrough(self):
        text = "यह हिंदी में है।"
        result = normalize_romanized_query(text)
        assert result == text

    def test_empty_string(self):
        result = normalize_romanized_query("")
        assert result == ""

    def test_whitespace_only(self):
        result = normalize_romanized_query("   ")
        assert result == "   "

    def test_mixed_scripts(self):
        result = normalize_romanized_query(
            "This is mixed with हिंदी and English."
        )
        assert isinstance(result, str)
