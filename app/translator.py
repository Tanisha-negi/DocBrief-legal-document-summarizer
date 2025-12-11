from transformers import pipeline

# ----------------------------------------------------
# ✅ CRITICAL FIX: Load the model ONCE globally when the module starts.
# We will use this global variable inside the function.
# ----------------------------------------------------
try:
    DEFAULT_TRANSLATOR = pipeline("translation", model="Helsinki-NLP/opus-mt-en-hi")
    print("Default Hindi translation model loaded successfully.")
except Exception as e:
    print(f"FATAL: Could not load default translation model: {e}")
    DEFAULT_TRANSLATOR = None

def translate_text(text, target_lang="hi"):
    """
    Translates text from English to Hindi using the pre-loaded Helsinki-NLP model.
    NOTE: This function is simplified to only handle English-to-Hindi using the cached model.
    The routes file handles dynamic languages via its own cache.
    """
    if DEFAULT_TRANSLATOR is None:
        return "Translation service is currently unavailable."
        
    if not text or not text.strip():
        return "No text provided for translation."

    try:
        # ⚠️ FIX: Use the pre-loaded global pipeline
        return DEFAULT_TRANSLATOR(text)[0]['translation_text']
    except Exception as e:
        print(f"Error during translation: {e}")
        return "Translation failed due to a processing error."

# ----------------------------------------------------
# 💡 Note on Project Structure:
# Your routes.py is already handling dynamic language translation
# by caching models globally (TRANSLATION_PIPELINES = {}).
# This file (translator.py) is now set up efficiently, but you 
# might not need it if the routes handle all translation logic.
# ----------------------------------------------------