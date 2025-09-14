try:
    import fugashi
    tagger = fugashi.Tagger()
    FURIGANA_AVAILABLE = True
    print("DEBUG: Fugashi loaded successfully")
except Exception as e:
    print(f"DEBUG: Fugashi failed to load: {e}")
    # Fallback to MeCab if fugashi fails
    try:
        import MeCab
        import unidic_lite
        tagger = MeCab.Tagger(f"-d {unidic_lite.DICDIR}")
        FURIGANA_AVAILABLE = True
        print("DEBUG: MeCab loaded successfully as fallback")
    except Exception as e2:
        print(f"DEBUG: MeCab also failed to load: {e2}")
        tagger = None
        FURIGANA_AVAILABLE = False

print(f"DEBUG: FURIGANA_AVAILABLE = {FURIGANA_AVAILABLE}")

def text_to_ruby_html(text):
    """
    Convert Japanese text to HTML with <ruby> tags for all kanji words (熟語単位), using hiragana as furigana.
    """
    print(f"DEBUG: text_to_ruby_html called with: '{text}'")
    print(f"DEBUG: FURIGANA_AVAILABLE = {FURIGANA_AVAILABLE}, tagger = {tagger}")
    
    if not FURIGANA_AVAILABLE or not tagger:
        # Return original text if furigana is not available
        print("DEBUG: Furigana not available, returning original text")
        return text
    
    try:
        print(f"DEBUG: Processing with tagger type: {type(tagger)}")
        # Check if it's fugashi tagger by checking module type
        if str(type(tagger)).find('fugashi') != -1:  # fugashi tagger
            print("DEBUG: Using fugashi tagger")
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
            result_text = ''.join(result)
            print(f"DEBUG: Fugashi processing complete: {result_text}")
            return result_text
        else:  # MeCab tagger with unidic-lite
            print("DEBUG: Using MeCab tagger")
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
            result_text = ''.join(result)
            print(f"DEBUG: MeCab processing complete: {result_text}")
            return result_text
    except Exception as e:
        # Return original text if processing fails
        print(f"DEBUG: Exception in text_to_ruby_html: {e}")
        import traceback
        traceback.print_exc()
        return text 