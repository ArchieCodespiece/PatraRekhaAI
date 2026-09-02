import pytest
from services.language_detection import (
    detect_language,
    get_language_name,
)


class TestDetectLanguage:
    """Test the detect_language() function."""

    def test_english(self):
        result = detect_language(
            "This is a sample English document about AI."
        )
        assert result.language == "en"
        assert result.romanized is False

    def test_hindi_devanagari(self):
        result = detect_language(
            "यह एक हिंदी दस्तावेज़ है जो कृत्रिम बुद्धिमत्ता के बारे में है।"
        )
        assert result.language == "hi"
        assert "Devanagari" in result.scripts

    def test_bengali(self):
        result = detect_language(
            "এটি একটি বাংলা নথি যা কৃত্রিম বুদ্ধিমত্তা সম্পর্কে।"
        )
        assert result.language == "bn"
        assert "Bengali" in result.scripts

    def test_tamil(self):
        result = detect_language(
            "இது செயற்கை நுண்ணறிவு பற்றிய ஒரு தமிழ் ஆவணம்."
        )
        assert result.language == "ta"
        assert "Tamil" in result.scripts

    def test_telugu(self):
        result = detect_language(
            "ఇది కృత్రిమ మేధస్సు గురించి ఒక తెలుగు పత్రం."
        )
        assert result.language == "te"
        assert "Telugu" in result.scripts

    def test_marathi(self):
        result = detect_language(
            "हे कृत्रिम बुद्धिमत्ता बद्दल एक मराठी दस्तऐवज आहे."
        )
        assert result.language == "mr"
        assert "Devanagari" in result.scripts

    def test_gujarati(self):
        result = detect_language(
            "આ કૃત્રિમ બુદ્ધિમત્તા વિશે એક ગુજરાતી દસ્તાવેજ છે."
        )
        assert result.language == "gu"
        assert "Gujarati" in result.scripts

    def test_kannada(self):
        result = detect_language(
            "ಇದು ಕೃತಕ ಬುದ್ಧಿಮತ್ತೆ ಬಗ್ಗೆ ಒಂದು ಕನ್ನಡ ಡಾಕ್ಯುಮೆಂಟ್."
        )
        assert result.language == "kn"
        assert "Kannada" in result.scripts

    def test_malayalam(self):
        result = detect_language(
            "ഇത് കൃത്രിം ബുദ്ധിശക്തിയെ കുറിച്ചുള്ള ഒരു മലയാള ഡോക്യുമെന്റ്."
        )
        assert result.language == "ml"
        assert "Malayalam" in result.scripts

    def test_punjabi_gurmukhi(self):
        result = detect_language(
            "ਇਹ ਕ੍ਰਿਤਰਿਮ ਬੁੱਧੀਮੱਤੀ ਬਾਰੇ ਇੱਕ ਪੰਜਾਬੀ ਦਸਤਾਵੇਜ਼ ਹੈ."
        )
        assert result.language == "pa"
        assert "Gurmukhi" in result.scripts

    def test_odia(self):
        result = detect_language(
            "ଏହା କୃତ୍ରିମ ବୁଦ୍ଧିମତ୍ତା ବିଷୟରେ ଏକ ଓଡ଼ିଆ ଡକୁମେଣ୍ଟ."
        )
        assert result.language == "or"
        assert "Odia" in result.scripts

    def test_assamese(self):
        result = detect_language(
            "এটা কৃত্ৰিম বুদ্ধিমত্তাৰ বিষয়ত এটা অসমীয়া দস্তাবেজ."
        )
        assert result.language == "as"
        assert "Bengali" in result.scripts

    def test_romanized_hinglish(self):
        result = detect_language(
            "Mera naam Rahul hai aur main AI developer hoon."
        )
        assert result.language == "en"
        assert result.romanized is True

    def test_code_switched(self):
        result = detect_language(
            "This document is about Artificial Intelligence aur ismein Hindi bhi hai."
        )
        assert result.code_switched is True

    def test_confidence_range(self):
        result = detect_language("Hello world")
        assert 0.0 <= result.confidence <= 1.0

    def test_to_dict(self):
        result = detect_language("Test text")
        d = result.to_dict()
        assert "language" in d
        assert "languages" in d
        assert "script" in d
        assert "romanized" in d
        assert "code_switched" in d
        assert "confidence" in d


class TestGetLanguageName:
    """Test the get_language_name() function."""

    def test_english(self):
        assert get_language_name("en") == "English"

    def test_hindi(self):
        assert get_language_name("hi") == "Hindi"

    def test_bengali(self):
        assert get_language_name("bn") == "Bengali"

    def test_tamil(self):
        assert get_language_name("ta") == "Tamil"

    def test_unknown(self):
        assert get_language_name("xx") == "Unknown"
