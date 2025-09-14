#!/usr/bin/env python3
import sys
import os
sys.path.append('.')

# Test the updated onomatopoeia functionality
def test_onomatopoeia_data():
    print("Testing updated onomatopoeia data loading...")
    try:
        from onomatopoeia_data import get_onomatopoeia_list
        
        # Get onomatopoeia list
        onomatopoeia_list = get_onomatopoeia_list()
        print(f"Successfully loaded {len(onomatopoeia_list)} onomatopoeia items")
        
        # Check if example fields are available
        for i, item in enumerate(onomatopoeia_list[:3]):  # Check first 3 items
            print(f"\nItem {i+1}: {item['word']}")
            print(f"  Meaning: {item['meaning']}")
            print(f"  Has example1: {'example1' in item}")
            print(f"  Has example2: {'example2' in item}")
            print(f"  Has translation_example1: {'translation_example1' in item}")
            print(f"  Has translation_example2: {'translation_example2' in item}")
            
            if 'example1' in item:
                print(f"  Example1: {item['example1']}")
            if 'translation_example1' in item:
                print(f"  Translation1: {item['translation_example1']}")
        
        return True
    except Exception as e:
        print(f"Error testing onomatopoeia data: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_quiz_generation():
    print("\nTesting quiz generation with updated logic...")
    try:
        os.environ.setdefault('OPENAI_API_KEY', 'dummy')
        os.environ.setdefault('SECRET_KEY', 'test')
        os.environ.setdefault('ONOMATOPOEIA_SHEET_ID', '')
        
        from app import get_today_quiz
        
        # Test quiz generation
        quiz = get_today_quiz()
        print(f"Generated quiz for word: {quiz['onomatope']}")
        print(f"Meaning: {quiz['correct_meaning_en']}")
        print(f"Examples: {quiz['examples']}")
        print(f"English translations: {quiz['examples_en']}")
        
        return True
    except Exception as e:
        print(f"Error testing quiz generation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success1 = test_onomatopoeia_data()
    success2 = test_quiz_generation()
    
    if success1 and success2:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)