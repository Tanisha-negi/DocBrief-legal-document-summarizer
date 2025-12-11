# 📄 DocBrief: AI-Powered Legal Document Summarizer

### 💡 Overview

DocBrief is an advanced **AI-powered** tool that leverages **Natural Language Processing (NLP)** techniques to automate legal document analysis. Designed for legal professionals and researchers, it rapidly processes lengthy contracts, case files, and regulatory documents to deliver essential insights, drastically reducing document review time.

### ✨ Core Features & Value

DocBrief offers a robust suite of features to ensure comprehensive and accurate analysis:

* **Multilingual Summaries:** Translates generated summaries and extracted key data into various user-preferred languages, facilitating international legal collaboration.
* **Extractive Summarization:** Generates highly accurate summaries by extracting the most critical, factually sound sentences directly from the source text, ensuring traceability.
* **Key Entity Recognition (KER):** Automatically identifies and highlights critical legal entities, including **parties, dates, financial amounts, and jurisdiction**.
* **Input Flexibility:** Supports processing of various document formats (PDF, DOCX, TXT).

### ⚙️ Technology Highlights

| Layer | Category | Technology / Library | Purpose |
| :--- | :--- | :--- | :--- |
| **I. Frontend (Client)** | **User Interface** | **HTML5, CSS3** | Structure and styling of the web interface. |
| | **Interactivity** | **JavaScript (Vanilla)** | Client-side logic, dynamic content rendering, and form handling. |
| **II. Backend (Server/Core)** | **Core Language** | **Python** | Primary language for business logic, API definition, and NLP operations. |
| | **Web Framework** | Flask | Serving the REST API, managing routes, and handling request/response cycles. |
| | **NLP Engine** | Hugging Face Transformers, Spacy, NLTK | Implementing advanced deep learning models (e.g., BART, T5) for summarization and feature extraction. |
| | **Translation** | MarianMT (Hugging Face) or External API (Google/Microsoft) | Handling multilingual translation of summaries and key notes. |
| **III. Data/File Mgmt** | **Document Processing** | Pandas, PyPDF2, python-docx | Ingestion, parsing, and normalization of diverse document formats (PDF, DOCX, etc.). |
| **IV. Infrastructure** | **Containerization** | Docker | Packaging the application, environment, and dependencies for reliable deployment. |

### 🚀 Getting Started

Follow these steps to set up and run DocBrief locally:

#### Prerequisites

* Python 3.8+
* pip

#### Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/yourusername/DocBrief.git](https://github.com/Tanisha-negi/DocBrief-legal-document-summarizer.git)
    cd DocBrief_legal_document_summarizer
    ```

2.  **Setup Environment:** Create and activate a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application:**
    ```bash
    python app.py
    ```
    The application will typically be accessible at `http://127.0.0.1:5000`.


### 📜 License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
