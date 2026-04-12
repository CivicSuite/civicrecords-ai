import base64
import subprocess
from pathlib import Path
import httpx
from app.config import settings

MULTIMODAL_MODEL = "gemma4:26b"
OCR_PROMPT = "Extract all text from this image. Return only the extracted text, no commentary."

async def extract_text_multimodal(image_path: Path, model: str = MULTIMODAL_MODEL) -> str:
    image_bytes = image_path.read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={"model": model, "prompt": OCR_PROMPT, "images": [image_b64], "stream": False},
        )
        if resp.status_code == 200:
            return resp.json().get("response", "")
        raise RuntimeError(f"Ollama multimodal failed: {resp.status_code} {resp.text}")

def extract_text_tesseract(image_path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(image_path)
        return pytesseract.image_to_string(img)
    except ImportError:
        raise RuntimeError("pytesseract or Pillow not installed — cannot use Tesseract fallback")
    except Exception as e:
        raise RuntimeError(f"Tesseract OCR failed: {e}")

async def extract_text_from_image(image_path: Path, prefer_multimodal: bool = True, model: str = MULTIMODAL_MODEL) -> str:
    if prefer_multimodal:
        try:
            return await extract_text_multimodal(image_path, model)
        except Exception:
            pass
    return extract_text_tesseract(image_path)

async def extract_text_from_scanned_pdf(pdf_path: Path, prefer_multimodal: bool = True, model: str = MULTIMODAL_MODEL) -> list[dict]:
    from PIL import Image
    import io
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber required for scanned PDF processing")
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            img = page.to_image(resolution=200)
            img_bytes = io.BytesIO()
            img.original.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(img_bytes.read())
                tmp_path = Path(tmp.name)
            text = await extract_text_from_image(tmp_path, prefer_multimodal, model)
            pages.append({"text": text, "page_number": i})
            tmp_path.unlink(missing_ok=True)
    return pages
