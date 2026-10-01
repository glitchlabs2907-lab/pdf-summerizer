"""Explain every page of a lecture PDF in simpler language with Gemini."""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pypdf import PdfReader, PdfWriter


DEFAULT_PAGES_PER_CHUNK = 2
MAX_OUTPUT_TOKENS = 8192


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite a lecture PDF in simpler language without skipping content."
    )
    parser.add_argument("pdf", type=Path, help="Path to the lecture PDF")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Markdown output path (default: <pdf-name>_simplified.md)",
    )
    parser.add_argument(
        "--pages-per-chunk",
        type=int,
        default=DEFAULT_PAGES_PER_CHUNK,
        help=f"Pages to explain per request (default: {DEFAULT_PAGES_PER_CHUNK})",
    )
    args = parser.parse_args()
    if args.pages_per_chunk < 1:
        parser.error("--pages-per-chunk must be at least 1")
    return args


def pdf_chunks(
    reader: PdfReader, pages_per_chunk: int
) -> Iterator[tuple[int, int, bytes]]:
    """Yield one-based page ranges and PDF bytes for each page batch."""
    for start_index in range(0, len(reader.pages), pages_per_chunk):
        end_index = min(start_index + pages_per_chunk, len(reader.pages))
        writer = PdfWriter()
        for page_index in range(start_index, end_index):
            writer.add_page(reader.pages[page_index])
        buffer = io.BytesIO()
        writer.write(buffer)
        yield start_index + 1, end_index, buffer.getvalue()


def make_prompt(start_page: int, end_page: int) -> str:
    return f"""You are an expert, careful lecture-note tutor. Explain the attached PDF pages {start_page}-{end_page} in clear, beginner-friendly language.

Completeness is essential. Work through every page in order and preserve every distinct idea and useful detail. Do not turn this into a short summary or omit material because it seems repetitive or minor. Include:
- every heading, definition, claim, step, example, exception, and caveat;
- equations and symbols, with a plain-language explanation of what they mean;
- all meaningful entries in tables, and the labels, parts, and relationships in diagrams or figures;
- references to the original page number wherever helpful.

Use headings that follow the source structure. Explain technical terms when first introduced. Keep the original meaning, and do not add unsupported facts. If text or a figure is unclear, explicitly identify the page and what could not be read instead of guessing. Return only the rewritten lesson for these pages."""


def simplify_pdf(
    pdf_path: Path,
    output_path: Path,
    pages_per_chunk: int,
    client: genai.Client,
    model: str,
) -> None:
    reader = PdfReader(str(pdf_path))
    if reader.is_encrypted:
        raise ValueError("This PDF is password-protected. Unlock it and try again.")
    if not reader.pages:
        raise ValueError("The PDF has no pages to process.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output:
        output.write(f"# Simplified lecture notes: {pdf_path.stem}\n\n")
        output.write(f"Source: {pdf_path.name} ({len(reader.pages)} pages)\n")
        output.write("\n---\n")
        output.flush()

        chunks = pdf_chunks(reader, pages_per_chunk)
        for chunk_number, (start_page, end_page, pdf_bytes) in enumerate(chunks, start=1):
            print(
                f"Processing pages {start_page}-{end_page} "
                f"({chunk_number} of {(len(reader.pages) + pages_per_chunk - 1) // pages_per_chunk})...",
                flush=True,
            )
            pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
            response = client.models.generate_content(
                model=model,
                contents=[pdf_part, make_prompt(start_page, end_page)],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                ),
            )
            candidates = response.candidates or []
            if (
                candidates
                and candidates[0].finish_reason == types.FinishReason.MAX_TOKENS
            ):
                raise RuntimeError(
                    f"Gemini reached its output limit for pages {start_page}-{end_page}. "
                    "That batch was not written; rerun with a smaller --pages-per-chunk value."
                )
            explanation = response.text
            if not explanation or not explanation.strip():
                raise RuntimeError(
                    f"Gemini returned no text for pages {start_page}-{end_page}. "
                    "The partial output has been kept."
                )
            output.write(f"\n\n## Pages {start_page}-{end_page}\n\n")
            output.write(explanation.strip())
            output.write("\n")
            output.flush()

    print(f"Done. Simplified notes saved to: {output_path}")


def main() -> int:
    args = parse_args()
    pdf_path = args.pdf.expanduser().resolve()
    if not pdf_path.is_file():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        return 2
    if pdf_path.suffix.lower() != ".pdf":
        print("Error: input file must have a .pdf extension.", file=sys.stderr)
        return 2

    output_path = args.output or pdf_path.with_name(f"{pdf_path.stem}_simplified.md")
    output_path = output_path.expanduser().resolve()
    if output_path == pdf_path:
        print("Error: output path cannot overwrite the input PDF.", file=sys.stderr)
        return 2

    load_dotenv(Path(__file__).with_name(".env"))
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "").strip()
    if not api_key or api_key.lower() == "your_gemini_api_key_here":
        print("Error: set your key in GEMINI_API_KEY in the .env file.", file=sys.stderr)
        return 2
    if not model or model.lower() == "your_gemini_model_name":
        print("Error: set a model name in GEMINI_MODEL in the .env file.", file=sys.stderr)
        return 2

    try:
        client = genai.Client(api_key=api_key)
        simplify_pdf(pdf_path, output_path, args.pages_per_chunk, client, model)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())