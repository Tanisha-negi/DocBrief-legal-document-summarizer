from transformers import pipeline, AutoTokenizer
import re
import logging

# ----------------------------------------------------
# ⚙️ GLOBAL CONFIGURATION AND MODEL LOADING
# ----------------------------------------------------
MODEL_NAME = "facebook/bart-large-cnn"
# BART's hard limit is 1024 tokens. We set a slightly lower chunk size 
# to leave room for special start/end tokens added by the model.
MAX_MODEL_INPUT_TOKENS = 1024
CHUNK_SIZE = MAX_MODEL_INPUT_TOKENS - 50 

try:
    # Load the Summarization Pipeline (Model)
    SUMMARIZER_PIPELINE = pipeline(
        "summarization", 
        model=MODEL_NAME
        # Optional: Add device=0 for GPU if available and configured
    )
    # Load the Tokenizer (Critical for accurate chunking)
    SUMMARIZER_TOKENIZER = AutoTokenizer.from_pretrained(MODEL_NAME)
    print("BART summarization model and tokenizer loaded successfully.")
except Exception as e:
    print(f"FATAL: Could not load summarization model. Summarization will fail: {e}")
    SUMMARIZER_PIPELINE = None
    SUMMARIZER_TOKENIZER = None


# ----------------------------------------------------
# 🧱 UTILITY: CHUNKING LOGIC
# ----------------------------------------------------

def get_text_chunks(long_text):
    """
    Splits long text into token-sized chunks suitable for the BART model's input limit.
    """
    if SUMMARIZER_TOKENIZER is None:
        return []

    # Encode the entire text without truncation
    tokens = SUMMARIZER_TOKENIZER.encode(long_text, truncation=False)
    
    tokenized_chunks = []
    
    # Iterate and split tokens based on the defined CHUNK_SIZE
    for i in range(0, len(tokens), CHUNK_SIZE):
        chunk = tokens[i:i + CHUNK_SIZE]
        # Decode the chunk back to text, skipping special tokens
        tokenized_chunks.append(SUMMARIZER_TOKENIZER.decode(chunk, skip_special_tokens=True))
        
    return tokenized_chunks


# ----------------------------------------------------
# 📝 CORE SUMMARIZATION FUNCTIONS (Map-Reduce Implemented Here)
# ----------------------------------------------------

summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

def summarize_text(text):
    """
    Generates a single, paragraph-style summary. Handles chunking for long input.
    """
    if SUMMARIZER_PIPELINE is None:
        return "Summarization service is currently unavailable."
        
    if not text or not text.strip():
        return "No text provided for summarization."

    # First, check if the text is too long for a single pass
    if len(SUMMARIZER_TOKENIZER.encode(text, truncation=False)) > MAX_MODEL_INPUT_TOKENS:
        # If it's too long, run the Map-Reduce logic
        return summarize_long_text_map_reduce(text)

    # If the text is short enough, run standard single-pass summarization
    try:
        # max_length/min_length control the length of the OUTPUT summary
        summary = SUMMARIZER_PIPELINE(text, max_length=300, min_length=100, do_sample=False)
        return summary[0]['summary_text']
    except Exception as e:
        print(f"Error during standard summarization: {e}")
        return "Summarization failed due to a processing error or resource issue."


def summarize_long_text_map_reduce(long_text):
    """
    Handles long text by:
    1. Mapping: Summarizing each chunk.
    2. Reducing: Combining and summarizing the resulting summaries recursively.
    """
    
    # 1. MAP (Summarize each chunk)
    tokenized_chunks = get_text_chunks(long_text)
    print(f"Document is too long ({len(tokenized_chunks)} chunks). Starting Map-Reduce...")
    
    chunk_summaries = []
    for i, chunk in enumerate(tokenized_chunks):
        # Recursively call the standard summarization function (which is safe now)
        summary = summarize_text(chunk) 
        if "failed" not in summary: # Simple check to filter errors
            chunk_summaries.append(summary)
        else:
             print(f"Warning: Chunk {i+1} failed to summarize.")

    if not chunk_summaries:
        return "Could not generate any intermediate summaries from the document chunks."

    # 2. REDUCE (Combine and summarize the summaries)
    combined_summaries = " ".join(chunk_summaries)
    
    # Final reduction call: The result is passed back into summarize_text,
    # which will automatically check the length and, if the combined summaries
    # are STILL too long, it will recursively chunk and summarize THEM.
    print(f"Starting final Reduction pass on combined summaries.")
    final_summary = summarize_text(combined_summaries)
        
    return final_summary

def chunk_text(text, max_chars=2000):
    """
    Splits long text into smaller chunks for faster summarization.
    """
    chunks = []
    while len(text) > max_chars:
        split_at = text.rfind("\n", 0, max_chars)
        if split_at == -1:
            split_at = max_chars
        chunks.append(text[:split_at].strip())
        text = text[split_at:]
    if text.strip():
        chunks.append(text.strip())
    return chunks

def summarize_text(text, max_length=150, min_length=40):
    try:
        result = summarizer(text, max_length=max_length, min_length=min_length, do_sample=False)
        return result[0]['summary_text']
    except Exception as e:
        logging.exception(f"Summarization failed: {e}")
        return ""


def summarize_to_bullets(text):
    """
    Summarizes text into bullet points, chunk by chunk.
    """
    bullets = []
    chunks = chunk_text(text)

    for i, chunk in enumerate(chunks):
        try:
            # Replace this with your actual summarizer call
            summary = summarize_text(chunk)  
            if summary:
                bullets.append(f"Point {i+1}: {summary}")
        except Exception as e:
            logging.exception(f"Summarization failed for chunk {i+1}: {e}")
            bullets.append(f"Chunk {i+1}: [summary unavailable]")

    return bullets

# ----------------------------------------------------
# 💡 NEW FEATURE ADDED: Key Term Extraction (Placeholder)
# ----------------------------------------------------

def extract_key_terms(text):
    """
    Extracts key terms and generates a dictionary of term: definition.
    This function currently returns a placeholder structure.
    """
    return {
        "Token": "The basic unit of text processing for AI models (about 3/4 of a word).",
        "Map-Reduce": "A technique used for summarizing long texts by dividing them into chunks (Map) and combining their summaries (Reduce).",
        "Context Window": "The maximum amount of text (tokens) an AI model can process in a single request.",
        "Indemnification": "A contractual clause protecting a party from financial losses in specified circumstances."
    }