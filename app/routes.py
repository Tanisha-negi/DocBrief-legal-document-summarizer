from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session, make_response, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from .models import db, Document
from .summarizer import summarize_text, summarize_to_bullets
from .parser import extract_text_from_file
from difflib import get_close_matches
from transformers import pipeline
from fpdf import FPDF # Used for dynamic PDF generation
from deep_translator import GoogleTranslator
import logging, time
from requests.exceptions import RequestException
from flask_mail import Message, Mail
from typing import Callable, Optional


main = Blueprint('main', __name__)

# Efficiency Fix: Global Cache for Translation Models
TRANSLATION_PIPELINES = {}

# --- PUBLIC ROUTES ---

@main.route("/", methods=["GET"])
def home():
    """Serves the home page containing the file upload form."""
    return render_template("home.html")

@main.route("/summarize-doc", methods=["POST"])
def summarize_doc():
    """
    Handles file upload and processing. Saves summary to SESSION for guests,
    or DB for logged-in users. Supports both bullet and simple summary types.
    """
    import os
    import uuid
    import logging
    from werkzeug.utils import secure_filename

    # Get upload and form
    upload = request.files.get("document")
    summary_type = request.form.get("summary_type", "bullets")

    if not upload or upload.filename == "":
        flash("No file uploaded.")
        return redirect(url_for("main.home"))

    # Normalize names and paths
    filename = secure_filename(upload.filename) or f"upload_{uuid.uuid4().hex}.txt"
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    try:
        # Save directly to final per-user folder if authenticated, otherwise use temp then session
        if current_user.is_authenticated:
            user_folder = os.path.join(project_root, "uploads", str(current_user.id))
            os.makedirs(user_folder, exist_ok=True)

            unique_name = f"{uuid.uuid4().hex}_{filename}"
            final_path = os.path.join(user_folder, unique_name)

            # Save file straight to final path (avoids fragile temp->move)
            upload.save(final_path)
            logging.info("Saved upload to %s", final_path)
            source_path = final_path
        else:
            # Guest: save to temp folder, will remove later
            temp_folder = os.path.join(project_root, "temp_uploads")
            os.makedirs(temp_folder, exist_ok=True)

            unique_name = f"{uuid.uuid4().hex}_{filename}"
            temp_path = os.path.join(temp_folder, unique_name)
            upload.save(temp_path)
            logging.info("Saved guest upload to %s", temp_path)
            source_path = temp_path

        # Ensure file exists before processing
        if not os.path.exists(source_path):
            flash("Uploaded file could not be saved. Try again.")
            return redirect(url_for("main.home"))

        # Extract and summarize
        text = extract_text_from_file(source_path)
        if not text or not text.strip():
            flash("Could not extract text from the file.")
            if not current_user.is_authenticated and os.path.exists(source_path):
                os.remove(source_path)
            return redirect(url_for("main.home"))

        if summary_type == "simple":
            summary = summarize_text(text) or ""
            bullet_points = [summary] if summary else []
        else:
            bullet_points = summarize_to_bullets(text) or []
            summary = "\n".join(bullet_points)

        if not summary.strip():
            if not current_user.is_authenticated and os.path.exists(source_path):
                os.remove(source_path)
            return render_template(
                "result.html",
                document_title=filename,
                bullet_points=[],
                summary_type=summary_type,
                key_terms={},
                error=True,
            )

        key_terms = {}  # placeholder

        if current_user.is_authenticated:
            # Save DB entry with absolute final_path (already saved)
            doc = Document(
                filename=filename,
                filepath=final_path,
                summary=summary,
                user_id=current_user.id,
            )
            db.session.add(doc)
            db.session.commit()
            logging.info("Document saved with ID: %s", doc.id)
            return redirect(
                url_for("main.view_summary", doc_id=doc.id, summary_type=summary_type)
            )
        else:
            # Guest flow: store summary in session, remove temp file
            session["guest_summary"] = summary
            session["guest_filename"] = filename
            session["guest_summary_type"] = summary_type

            # cleanup temp file
            try:
                if os.path.exists(source_path):
                    os.remove(source_path)
                    logging.info("Removed guest temp file %s", source_path)
            except Exception:
                logging.exception("Failed to remove guest temp file")

            return render_template(
                "result.html",
                document_title=filename,
                bullet_points=bullet_points,
                summary_type=summary_type,
                key_terms=key_terms,
            )

    except Exception as exc:
        logging.exception("Error in summarize_doc: %s", exc)
        flash("An unexpected error occurred while processing the file.")
        # Attempt cleanup of any saved temp file
        try:
            if "source_path" in locals() and os.path.exists(source_path) and not current_user.is_authenticated:
                os.remove(source_path)
        except Exception:
            logging.debug("Cleanup failed")
        return redirect(url_for("main.home"))

# --- MERGED FEATURE ROUTES ---





try:
    from deep_translator import GoogleTranslator as DeepGoogleTranslator
except Exception:
    DeepGoogleTranslator = None

# Google Cloud Translate client (optional; requires GOOGLE_APPLICATION_CREDENTIALS or explicit key)
GOOGLE_CLOUD_AVAILABLE = False
try:
    from google.cloud import translate_v2 as translate_v2
    GOOGLE_CLOUD_AVAILABLE = True
except Exception:
    GOOGLE_CLOUD_AVAILABLE = False

# Module-level model map and cache
HF_MODEL_MAP = {
    "hi": "Helsinki-NLP/opus-mt-en-hi",
    "bn": "Helsinki-NLP/opus-mt-en-bn",
    "es": "Helsinki-NLP/opus-mt-en-es",
    "fr": "Helsinki-NLP/opus-mt-en-fr",
    # add only verified HF model ids here
}
TRANSLATION_PIPELINES = {}


# If deep_translator expects alternative codes, map here
FALLBACK_CODE_MAP = {
    "zh": "zh",
    "zh-cn": "zh",
    "zh-tw": "zh-TW",
    # add other special cases if necessary
}

def _get_hf_pipeline(lang: str):
    """Return HF pipeline if mapped and loadable, else None."""
    model_id = HF_MODEL_MAP.get(lang)
    if not model_id:
        return None
    try:
        pipe = pipeline("translation", model=model_id)
        logging.info("Loaded HF pipeline %s for %s", model_id, lang)
        return pipe
    except Exception:
        logging.exception("Failed to load HF model %s", model_id)
        return None

def _get_google_cloud_translator():
    """Return a callable(text, target) -> str using Google Cloud Translate if available, else None."""
    if not GOOGLE_CLOUD_AVAILABLE:
        return None
    try:
        client = translate_v2.Client()
        def gc_translate(text: str, target: str):
            result = client.translate(text, target_language=target)
            return result.get("translatedText", "[translation unavailable]")
        return gc_translate
    except Exception:
        logging.exception("Failed to initialize Google Cloud Translate client")
        return None

def _get_deep_translator_callable(lang: str) -> Optional[Callable[[str], str]]:
    """Return a deep-translator callable or None if package missing."""
    if DeepGoogleTranslator is None:
        return None
    target = FALLBACK_CODE_MAP.get(lang, lang)
    def gt(text: str, target_code=target):
        return DeepGoogleTranslator(source="auto", target=target_code).translate(text)
    return gt

def get_translator(lang: str):
    """
    Return a translator backend:
      - HF pipeline object if available
      - else Google Cloud callable (text, target) if available
      - else deep_translator callable (text) if available
      - else None
    Cache results in TRANSLATION_PIPELINES.
    """
    if lang in TRANSLATION_PIPELINES:
        return TRANSLATION_PIPELINES[lang]

    # 1) Try HF
    pipe = _get_hf_pipeline(lang)
    if pipe:
        TRANSLATION_PIPELINES[lang] = pipe
        return pipe

    # 2) Try Google Cloud Translate (preferred fallback)
    gc = _get_google_cloud_translator()
    if gc:
        # wrap to a consistent callable signature translator(text) -> str for single-target usage
        def gc_wrapper(text: str, target=lang):
            return gc(text, target)
        TRANSLATION_PIPELINES[lang] = gc_wrapper
        logging.info("Using Google Cloud Translate fallback for %s", lang)
        return gc_wrapper

    # 3) Try deep-translator
    dt = _get_deep_translator_callable(lang)
    if dt:
        TRANSLATION_PIPELINES[lang] = dt
        logging.info("Using deep_translator fallback for %s", lang)
        return dt

    TRANSLATION_PIPELINES[lang] = None
    logging.warning("No translator available for %s", lang)
    return None

def translate_with_retry_callable(translator_callable: Callable[[str], str], text: str,
                                  attempts: int = 4, base_delay: float = 0.6) -> str:
    """Retry wrapper for callable translators (deep_translator / google cloud wrapper)."""
    for attempt in range(1, attempts + 1):
        try:
            return translator_callable(text)
        except RequestException as e:
            logging.warning("Translation attempt %s RequestException: %s", attempt, e)
        except Exception:
            logging.exception("Translation attempt %s failed", attempt)
        time.sleep(base_delay * attempt)
    return "[translation unavailable]"

@main.route("/translate/<lang>")
def translate(lang):
    """
    Translate document summary text only (saved doc via doc_id or guest session).
    Uses HF models when available, otherwise Google Cloud Translate (if configured),
    otherwise deep_translator with retries. Does NOT change UI or session locale.
    """
    doc_id = request.args.get("doc_id")

    # Load source summary (DB for logged-in, session for guest)
    if doc_id and current_user.is_authenticated:
        doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
        summary_text = doc.summary or ""
        filename = doc.filename
        summary_type = request.args.get("summary_type", "bullets")
        key_terms = {}
    else:
        summary_text = session.get("guest_summary")
        filename = session.get("guest_filename", "Summary")
        summary_type = session.get("guest_summary_type", "bullets")
        key_terms = {}
        doc = None
        if not summary_text:
            flash("No active summary session found. Please upload a file.")
            return redirect(url_for("main.home"))

    # Prepare plain bullet points only
    bullet_points = [p.strip() for p in summary_text.split("\n") if p.strip()]

    # Acquire translator backend
    translator = get_translator(lang)
    if translator is None:
        flash("Translation for the selected language is not available right now.")
        return redirect(url_for("main.view_summary", doc_id=doc_id) if doc_id else url_for("main.home"))

    translated = []
    try:
        # Determine if translator is HF pipeline (has attributes .model or .tokenizer)
        is_hf = hasattr(translator, "model") or hasattr(translator, "tokenizer")

        if is_hf:
            # HF pipeline supports batching; use chunks
            chunk_size = 8
            for i in range(0, len(bullet_points), chunk_size):
                chunk = bullet_points[i : i + chunk_size]
                outputs = translator(chunk, max_length=2000)
                for out in outputs:
                    # Normalize HF outputs
                    if isinstance(out, dict) and "translation_text" in out:
                        translated.append(out["translation_text"])
                    elif isinstance(out, list) and out and isinstance(out[0], dict) and "translation_text" in out[0]:
                        translated.append(out[0]["translation_text"])
                    else:
                        translated.append(str(out))
        else:
            # translator is a callable(text) -> str. Use retry wrapper per bullet.
            for pt in bullet_points:
                translated.append(translate_with_retry_callable(translator, pt))

    except Exception:
        logging.exception("Translation process failed for lang %s", lang)
        flash("Translation failed. Please try another language or try again later.")
        return redirect(url_for("main.view_summary", doc_id=doc_id) if doc_id else url_for("main.home"))

    # Only render translated content to template; don't overwrite UI strings or session locale
    return render_template(
        "result.html",
        doc=doc,
        translated_points=translated,
        lang=lang,
        document_title=filename,
        summary_type=summary_type,
        bullet_points=bullet_points,
        key_terms=key_terms,
        full_text=None,
        bullet=None,
    )



from fpdf import FPDF # Assuming this is installed correctly
from flask import make_response # make_response is essential for this route
import os # For os.path.splitext

@main.route("/download-summary")
def download_summary():
    """
    Allows download of the summary PDF. Works for GUEST sessions (data in session) 
    or SAVED documents (by doc_id in query).
    """
    doc_id = request.args.get('doc_id')
    
    # --- 1. DETERMINE SOURCE (DB or SESSION) ---
    if doc_id and current_user.is_authenticated:
        # LOGGED-IN USER: PULL FROM DB (SECURE ACCESS)
        doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
        summary_text = doc.summary
        filename = doc.filename
    else:
        # GUEST USER: PULL FROM SESSION
        summary_text = session.get('guest_summary')
        filename = session.get('guest_filename', 'summary')
        if not summary_text:
            flash("No active summary session found.")
            return redirect(url_for("main.home"))
            
    # --- 2. GENERATE PDF CONTENT ---
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.write(8, f"Document Summary: {filename}\n\n")
    pdf.set_font("Arial", size=10)
    
    # Process text for PDF, replacing newlines for multi_cell compatibility
    pdf.multi_cell(0, 5, summary_text.replace('\n', '\n\n')) 
    
    # --- 3. CREATE RESPONSE (CRITICAL FIX) ---
    
    # Get binary output and convert it to bytes
    binary_pdf_data = bytes(pdf.output(dest='S'))
    
    # Create response and set headers
    response = make_response(binary_pdf_data)
    response.headers.set('Content-Disposition', 'attachment', 
                         filename=f'{os.path.splitext(filename)[0]}_summary.pdf')
    response.headers.set('Content-Type', 'application/pdf')
    
    return response


# --- Add this new route to routes.py ---

@main.route("/download-translated-summary/<lang>", methods=['GET'])
def download_translated_summary(lang):
    """
    Translates the summary to the specified language (lang) and generates a PDF.
    Works for SAVED documents (doc_id) or GUEST sessions.
    """
    from fpdf import FPDF
    
    doc_id = request.args.get('doc_id')

    # --- 1. GET ORIGINAL SUMMARY TEXT ---
    if doc_id and current_user.is_authenticated:
        # Logged-in user: Get data from DB
        doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
        original_summary = doc.summary
        filename = doc.filename
    else:
        # Guest user: Get data from Session
        original_summary = session.get('guest_summary')
        filename = session.get('guest_filename', 'summary')
        if not original_summary:
            flash("No active summary session found for download.")
            return redirect(url_for("main.home"))

    # --- 2. TRANSLATE TEXT (Reusing Caching Logic) ---
    if lang not in TRANSLATION_PIPELINES:
        TRANSLATION_PIPELINES[lang] = pipeline("translation", model=f"Helsinki-NLP/opus-mt-en-{lang}")
    translator = TRANSLATION_PIPELINES[lang]
    
    # Translate the summary text (handle the entire block at once for better context)
    translated_output = translator(original_summary, max_length=512)[0]['translation_text']

    # --- 3. GENERATE PDF FROM TRANSLATED TEXT ---
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # NOTE: You may need a font that supports Indian scripts (e.g., Arial Unicode MS) 
    # if FPDF's default Arial doesn't render them correctly.
    pdf.set_font("Arial", size=12)
    pdf.write(8, f"Translated Summary ({lang.upper()}):\n\n")
    pdf.set_font("Arial", size=10)
    
    # Write the translated text
    pdf.multi_cell(0, 5, translated_output) 
    
    # --- 4. RETURN RESPONSE ---
    binary_pdf_data = bytes(pdf.output(dest='S'))
    response = make_response(binary_pdf_data)
    response.headers.set('Content-Disposition', 'attachment', 
                         filename=f'{os.path.splitext(filename)[0]}_{lang.upper()}_summary.pdf')
    response.headers.set('Content-Type', 'application/pdf')
    
    return response
# --- SECURED ROUTES (For accessing saved files) ---

@main.route("/dashboard")
@login_required 
def dashboard():
    documents = Document.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard.html", documents=documents)

@main.route("/view-summary/<int:doc_id>")
@login_required 
def view_summary(doc_id):
    doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
    summary_type = request.args.get("summary_type", "bullets")
    bullet_points = doc.summary.split("\n") if summary_type == "bullets" else [doc.summary]
    key_terms = {} # Placeholder

    return render_template("result.html", 
                           doc=doc, 
                           document_title=doc.filename,
                           bullet_points=bullet_points, 
                           summary_type=summary_type,
                           key_terms=key_terms)

@main.route("/highlight/<int:doc_id>/<int:point_index>")
@login_required 
def highlight(doc_id, point_index):
    doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
    bullet_points = doc.summary.split("\n")

    try:
        bullet = bullet_points[point_index]
    except IndexError:
        flash("Invalid summary point index.")
        return redirect(url_for("main.view_summary", doc_id=doc_id))

    text = extract_text_from_file(doc.filepath)
    sentences = text.split(". ")

    matches = get_close_matches(bullet, sentences, n=3, cutoff=0.5)
    highlighted = text
    for m in matches:
        highlighted = highlighted.replace(m, f"<mark>{m}</mark>")

    summary_type = request.args.get("summary_type", "bullets")
    return render_template(
        "highlight.html",
        full_text=highlighted,
        bullet=bullet,
        doc_id=doc_id,
        summary_type=summary_type
    )


@main.route("/delete/<int:doc_id>", methods=["POST"])
@login_required
def delete_document(doc_id):
    doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()

    # Optional: delete the file from disk
    if os.path.exists(doc.filepath):
        os.remove(doc.filepath)

    db.session.delete(doc)
    db.session.commit()
    flash("Document deleted successfully.")
    return redirect(url_for("main.dashboard"))

@main.route("/download/<int:doc_id>")
@login_required 
def download(doc_id):
    """Downloads the original file, correcting the path based on the project root."""
    doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
    
    # 1. Get the path components needed to rebuild the root
    app_dir = os.path.dirname(os.path.abspath(__file__)) 
    project_root = os.path.abspath(os.path.join(app_dir, "..")) 
    
    # 2. Reconstruct the absolute path using the saved segment
    # doc.filepath contains: 'uploads/1/filename.txt'
    # We combine project_root + doc.filepath to get the CORRECT path:
    # E:\...\legal_document_summarizer + uploads/1/filename.txt
    
    # NOTE: We use os.path.join with the full path to ensure it's correct
    absolute_filepath = os.path.join(project_root, doc.filepath)
    
    # Check if the file exists at the correct location
    if not os.path.exists(absolute_filepath):
        flash("Error: File not found at the expected location. The file may have been moved or deleted.")
        # If the file is missing, redirect to dashboard.
        return redirect(url_for('main.dashboard')) 
    
    # 3. Use the verified absolute path
    return send_file(absolute_filepath, as_attachment=True)
    doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()

    if not os.path.exists(doc.filepath):
        flash("File not found. It may have been deleted or moved.")
        return redirect(url_for("main.view_summary", doc_id=doc.id))

    return send_file(doc.filepath, as_attachment=True)
    doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()

    if not os.path.exists(doc.filepath):
        flash("File not found. It may have been deleted or moved.")
        return redirect(url_for("main.view_summary", doc_id=doc.id))

    return send_file(doc.filepath, as_attachment=True)


@main.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        # handle form submission
        name = request.form.get("name")
        message = request.form.get("message")
        # process or save message
        flash("Thanks for contacting us!")
        return redirect(url_for("main.home"))
    # default GET → render the contact form
    return render_template("contact.html")

@main.route('/contact-submit', methods=['POST'])
def contact_submit():
    # Get user input
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    message_content = request.form.get('message')
    
    try:
        # Create the email message object
        msg = Message(
            subject=f'New Contact Inquiry from {full_name}',
            recipients=['your_support_email@yourcompany.com'], # <-- CHANGE THIS to your receiving email
            body=f"""
Name: {full_name}
Email: {email}
---
Message:
{message_content}
"""
        )
        
        # Access the mail object initialized in your app structure
        mail = current_app.extensions.get('mail') 
        if mail:
            mail.send(msg)
            flash('Thank you! Your message has been sent successfully.', 'success')
        else:
            flash('Email service is not configured correctly.', 'error')

    except Exception as e:
        print(f"ERROR SENDING EMAIL: {e}")
        flash('Sorry, there was an error sending your message.', 'error')
        
    return redirect(url_for('main.home'))