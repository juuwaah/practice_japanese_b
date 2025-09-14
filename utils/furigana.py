try:
    import fugashi
    tagger = fugashi.Tagger()
    FURIGANA_AVAILABLE = True
except Exception:
    # Fallback to MeCab if fugashi fails
    try:
        import MeCab
        import unidic_lite
        tagger = MeCab.Tagger(f"-d {unidic_lite.DICDIR}")
        FURIGANA_AVAILABLE = True
    except Exception:
        tagger = None
        FURIGANA_AVAILABLE = False

def text_to_ruby_html(text):
    """
    Convert Japanese text to HTML with <ruby> tags for all kanji words (熟語単位), using hiragana as furigana.
    """
    if not FURIGANA_AVAILABLE or not tagger:
        # Return original text if furigana is not available
        return text
    
    try:
        # Check if it's fugashi tagger by checking module type
        if str(type(tagger)).find('fugashi') != -1:  # fugashi tagger
            tokens = tagger(text)
            result = []
            for token in tokens:
                surface = token.surface
                # Get reading from fugashi features
                reading = None
                
                # Try different attributes for reading
                if hasattr(token.feature, 'kana'):
                    reading = token.feature.kana
                elif hasattr(token.feature, 'pron'):
                    reading = token.feature.pron
                elif hasattr(token.feature, 'reading'):
                    reading = token.feature.reading
                    
                if not reading or reading == '*':
                    reading = surface
                    
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
        else:  # MeCab tagger with unidic-lite
            parsed = tagger.parse(text)
            result = []
            lines = parsed.split('\n')
            for line in lines:
                if line == 'EOS' or line == '':
                    continue
                parts = line.split('\t')
                if len(parts) < 2:
                    continue
                surface = parts[0]
                # For unidic-lite: surface, reading, pronun, lemma, pos, ...
                reading = parts[1] if len(parts) > 1 else surface
                
                if reading:
                    # Convert katakana to hiragana
                    hira = ''.join(chr(ord(ch) - 0x60) if 'ァ' <= ch <= 'ン' else ch for ch in reading)
                else:
                    hira = surface
                
                # If token contains kanji, add ruby
                if any('\u4e00' <= ch <= '\u9fff' for ch in surface):
                    result.append(f'<ruby>{surface}<rt>{hira}</rt></ruby>')
                else:
                    result.append(surface)
            return ''.join(result)
    except Exception:
        # Return original text if processing fails
        return text 