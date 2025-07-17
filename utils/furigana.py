import fugashi

tagger = fugashi.Tagger()

def text_to_ruby_html(text):
    """
    Convert Japanese text to HTML with <ruby> tags for all kanji words (熟語単位), using hiragana as furigana.
    """
    tokens = tagger(text)
    result = []
    for token in tokens:
        surface = token.surface
        # Get reading (hiragana)
        # Try to use 'reading' (カタカナ) or 'pron' (発音), fallback to surface
        reading = token.feature.get('reading') or token.feature.get('pron') or surface
        # Convert katakana to hiragana
        if reading and reading != surface:
            hira = ''.join(chr(ord(ch) - 0x60) if 'ァ' <= ch <= 'ン' else ch for ch in reading)
        else:
            hira = surface
        # If token contains kanji, add ruby
        if any('\u4e00' <= ch <= '\u9fff' for ch in surface):
            result.append(f'<ruby>{surface}<rt>{hira}</rt></ruby>')
        else:
            result.append(surface)
    return ''.join(result) 