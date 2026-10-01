# PDF Lecture Simplifier

A terminal-based Python tool that explains a lecture PDF in simpler language using Google's Gemini API. It works through the PDF in page batches, keeps the original page order, and writes each completed batch to a Markdown file so partial progress is not lost if a request fails.

## Setup

From this folder, activate the included virtual environment and install the dependencies:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Edit `.env` and replace `your_gemini_api_key_here` with your Google AI Studio API key. `GEMINI_MODEL` is the model Gemini will use; the starter value is `gemini-2.5-flash`, and you can replace it with another model available to your account.

## Run

```powershell
python main.py "C:\path\to\lecture.pdf"

example: 
From the project folder, for a PDF in Downloads: 
python main.py "$HOME\Downloads\lecture notes.pdf"

if you put it in the project folder:
python main.py ".\lecture-notes.pdf"
```

By default, the result is saved beside the PDF as `<filename>_simplified.md`. Choose a different output path or batch size with:

```powershell
python main.py "C:\path\to\lecture.pdf" --output "C:\path\to\notes.md" --pages-per-chunk 2
```

The instructions sent to Gemini ask it to retain definitions, examples, equations, table contents, diagram relationships, and caveats. Since generated explanations can still miss details, compare the result with the source before relying on it as a complete replacement. Scanned or unclear content is identified when possible rather than guessed.