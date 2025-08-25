# -*- coding: utf-8 -*-
"""
FastAPI backend — VNHis2Image
1) /ner        : trích xuất spans bằng spaCy spancat_v5
2) /generate   : dịch VI->EN bằng Gemini rồi gọi Imagen 3 sinh ảnh
3) /progress   : stub tiến độ cho UI
4) /health, /  : kiểm tra tình trạng dịch vụ
"""
from __future__ import annotations

import os
import base64
from typing import Optional, Literal, List
from collections import defaultdict

import spacy
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dotenv import load_dotenv, find_dotenv
from google import genai
from google.genai import types

# ----- Load environment (.env ở root + .env cạnh file) -----
load_dotenv(find_dotenv(), override=True)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)


AspectRatioT = Literal["1:1", "3:4", "4:3", "9:16", "16:9"]
PeopleT = Literal["dont_allow", "allow_adult", "allow_all"]

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # bắt buộc
IMAGEN_MODEL = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")

TRANSLATE_MODEL = os.getenv("TRANSLATE_MODEL", "gemini-2.5-flash-preview-05-20") 
# IMAGEN_SAMPLE_SIZE = os.getenv("IMAGEN_SAMPLE_SIZE", "1K")
ALLOW_PEOPLE = os.getenv("ALLOW_PEOPLE", "allow_adult")
DEFAULT_MIME = os.getenv("IMAGEN_MIME", "image/png")
DEFAULT_NUM_IMAGES = int(os.getenv("IMAGEN_NUM_IMAGES", "1"))

# CORS
ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "*")
ALLOWED_METHODS = os.getenv("ALLOWED_METHODS", "GET,POST,OPTIONS")
ALLOWED_HEADERS = os.getenv("ALLOWED_HEADERS", "*")

# NER (spaCy spancat)
MODEL_PATH = os.getenv("MODEL_PATH", "models/spancat_v5/model-best")
SPANS_KEY = os.getenv("SPANS_KEY", "sc")
ACCEPTANCE_THRESHOLD = float(os.getenv("ACCEPTANCE_THRESHOLD", "0.5"))

# ----- Guards & clients -----
print(f"GOOGLE_API_KEY loaded: {'Yes' if GOOGLE_API_KEY else 'No'}")
if not GOOGLE_API_KEY:
    print("!!! CẢNH BÁO: GOOGLE_API_KEY chưa được thiết lập. Ứng dụng sẽ thất bại.")
    raise RuntimeError("GOOGLE_API_KEY is missing. Put it in .env or export it before running.")

client = genai.Client(api_key=GOOGLE_API_KEY)

try:
    nlp = spacy.load(MODEL_PATH)
    print(f"[OK] Đã tải mô hình spaCy tại: {MODEL_PATH}")
except Exception as e:
    nlp = None
    print(f"[LỖI] Không thể tải mô hình spaCy tại {MODEL_PATH}: {e}")

# ----- FastAPI app -----
app = FastAPI(title="VNHis2Image API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS.split(",")] if ALLOWED_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=[m.strip() for m in ALLOWED_METHODS.split(",")] if ALLOWED_METHODS else ["*"],
    allow_headers=[h.strip() for h in ALLOWED_HEADERS.split(",")] if ALLOWED_HEADERS else ["*"],
)

# ----- Types -----
AspectRatioT = Literal["1:1", "3:4", "4:3", "9:16", "16:9"]
SampleSizeT = Literal["1K", "2K"]
PeopleT = Literal["dont_allow", "allow_adult", "allow_all"]

class GenReq(BaseModel):
    prompt: str = Field(..., description="Prompt tiếng Việt hoặc prompt từ form.")
    aspect_ratio: Optional[AspectRatioT] = None # pyright: ignore[reportInvalidTypeForm]
    number_of_images: int = Field(DEFAULT_NUM_IMAGES, ge=1, le=4)
    mime_type: Literal["image/png", "image/jpeg"] = Field(DEFAULT_MIME)
    allow_people: PeopleT = Field(ALLOW_PEOPLE) # pyright: ignore[reportInvalidTypeForm]
    width: Optional[int] = None
    height: Optional[int] = None

class GenOut(BaseModel):
    image_base64: str
    model: str

class NERReq(BaseModel):
    text: str

class NERSpan(BaseModel):
    text: str
    label: str
    start: int
    end: int
    score: Optional[float] = None

class NEROut(BaseModel):
    spans: List[NERSpan]

class NerCompatOut(BaseModel):
    fields: dict[str, str]
    scores: dict[str, float | None]

# ----- Helpers -----
def _guess_aspect_ratio(width: Optional[int], height: Optional[int]) -> AspectRatioT: # pyright: ignore[reportInvalidTypeForm]
    if not width or not height or width <= 0 or height <= 0:
        return "1:1"
    r = width / float(height)
    ratios = {"1:1": 1.0, "3:4": 0.75, "4:3": 1.3333, "9:16": 0.5625, "16:9": 1.7777}
    return min(ratios.items(), key=lambda kv: abs(kv[1] - r))[0]  # type: ignore[return-value]

def _to_data_uri(image_bytes: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"


def _translate_vi_to_en(vietnamese_prompt: str) -> str:
    """
    Dịch prompt từ tiếng Việt sang tiếng Anh, tối ưu cho image generation
    """
    if not vietnamese_prompt or not vietnamese_prompt.strip():
        raise ValueError("empty_prompt")
    
    print(f"[DEBUG] Bắt đầu dịch prompt: '{vietnamese_prompt}'")
    
    try:
        translation_prompt = f"""Translate the following Vietnamese text to English for AI image generation. 
            Keep the translation concise, clear, and suitable for image generation (under 200 words).
            Focus on visual elements, style, and composition.

            Vietnamese text: {vietnamese_prompt}

            English translation:"""
        
        response = client.models.generate_content(
            model=TRANSLATE_MODEL,
            contents=translation_prompt
        )
        
        print(f"[DEBUG] Response nhận được:")
        print(f"  - Candidates: {len(response.candidates) if response.candidates else 0}")
        
        if not response.candidates:
            print("[LỖI DỊCH] Không có candidates")
            raise RuntimeError("translation_failed_no_candidates")
        
        candidate = response.candidates[0]
        text = ""
        
        if hasattr(candidate, 'content') and candidate.content:
            if hasattr(candidate.content, 'parts') and candidate.content.parts:
                part = candidate.content.parts[0]
                if hasattr(part, 'text'):
                    text = part.text
                else:
                    text = str(part)
            else:
                text = str(candidate.content)
        else:
            text = str(candidate)
        
        text = text.strip()
        
        prefixes_to_remove = [
            "Here's the translated English text, formatted for AI image generation:",
            "Here's the English translation:",
            "English translation:",
            "Translation:",
        ]
        
        for prefix in prefixes_to_remove:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1].strip()
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if '[title]' in line or '[organization]' in line or '[flora_fauna]' in line or '[concept]' in line:
                continue
            if line.startswith('**') and line.endswith('**'):
                continue
            if line and not line.startswith('*'):
                cleaned_lines.append(line)
        
        clean_text = ' '.join(cleaned_lines)
        
        print(f"[DEBUG] Text sau xử lý: '{clean_text}'")
        
        if not clean_text or len(clean_text.strip()) < 10:
            print("[LỖI DỊCH] Text quá ngắn hoặc không hợp lệ, sử dụng prompt gốc")
            return vietnamese_prompt
        
        if len(clean_text) > 500:
            sentences = clean_text.split('. ')
            clean_text = '. '.join(sentences[:3])
            if not clean_text.endswith('.'):
                clean_text += '.'
            
        print(f"[SUCCESS] Dịch thành công: '{clean_text}'")
        return clean_text
        
    except Exception as e:
        print(f"[LỖI DỊCH] Exception: {type(e).__name__}: {e}")
        print(f"[FALLBACK] Sử dụng prompt gốc: '{vietnamese_prompt}'")
        return vietnamese_prompt

def _generate_with_imagen(
    prompt_en: str,
    *,
    aspect_ratio: AspectRatioT, # pyright: ignore[reportInvalidTypeForm]
    number_of_images: int,
    mime_type: str,
    allow_people: PeopleT, # pyright: ignore[reportInvalidTypeForm]
) -> bytes:
    """
    Tạo ảnh với Imagen - đã loại bỏ sample_image_size không hỗ trợ
    """
    print(f"[DEBUG] Tạo ảnh với config:")
    print(f"  - prompt: {prompt_en}")
    print(f"  - aspect_ratio: {aspect_ratio}")
    print(f"  - number_of_images: {number_of_images}")
    print(f"  - mime_type: {mime_type}")
    print(f"  - allow_people: {allow_people}")
    
    try:
        cfg = types.GenerateImagesConfig(
            number_of_images=number_of_images,
            aspect_ratio=aspect_ratio,
            person_generation=allow_people,
            include_rai_reason=True,
            output_mime_type=mime_type,
        )
        
        print(f"[DEBUG] Gọi Imagen API...")
        resp = client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=prompt_en,
            config=cfg,
        )
        
    except Exception as e:
        print(f"[DEBUG] Lỗi với config đầy đủ: {e}")
        print("[DEBUG] Thử với config tối thiểu...")
        
        try:
            resp = client.models.generate_images(
                model=IMAGEN_MODEL,
                prompt=prompt_en,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="1:1",
                    person_generation="allow_adult",
                    output_mime_type="image/png",
                )
            )
        except Exception as e2:
            print(f"[LỖI] Cả config tối thiểu cũng thất bại: {e2}")
            raise e2
    
    print(f"[DEBUG] Response received: {len(resp.generated_images) if resp.generated_images else 0} images")
    
    if not resp.generated_images:
        if hasattr(resp, 'rai_reason') and resp.rai_reason:
            print(f"[LỖI TẠO ẢNH] Bị chặn. Lý do: {resp.rai_reason}")
            raise RuntimeError(f"image_blocked: {resp.rai_reason}")
        raise RuntimeError("no_image_generated")
        
    img_obj = resp.generated_images[0].image
    
    image_bytes = None
    for attr_name in ['image_bytes', 'bytes', 'data', '_image_bytes']:
        if hasattr(img_obj, attr_name):
            image_bytes = getattr(img_obj, attr_name)
            if image_bytes:
                print(f"[DEBUG] Found image data in attribute: {attr_name}")
                break
    
    if not image_bytes or not isinstance(image_bytes, (bytes, bytearray)):
        print(f"[DEBUG] Image object attributes: {dir(img_obj)}")
        print(f"[DEBUG] Image object type: {type(img_obj)}")
        raise RuntimeError("image_bytes_missing")
    
    print(f"[SUCCESS] Generated image: {len(image_bytes)} bytes")
    return bytes(image_bytes)

# ----- Routes -----
@app.get("/")
def root():
    return {"message": "VNHis2Image API. Use /health, /ner, /generate."}

@app.get("/health")
def health():
    return {
        "ok": True,
        "imagen_model": IMAGEN_MODEL,
        "translate_model": TRANSLATE_MODEL,
        "ner_loaded": bool(nlp is not None),
        "supports": {
            "aspect_ratio": ["1:1", "3:4", "4:3", "9:16", "16:9"],
            "mime": ["image/png", "image/jpeg"],
        },
        "notes": "Prompts are auto-translated VI→EN before Imagen generation.",
    }

@app.post("/ner", response_model=NerCompatOut)
def ner(req: NERReq):
    if nlp is None:
        raise HTTPException(status_code=500, detail="spaCy_model_not_loaded")
    if not req.text.strip():
        return NerCompatOut(fields={}, scores={})

    doc = nlp(req.text)
    spans = list(doc.spans.get(SPANS_KEY, []))

    best_text: dict[str, str] = {}
    best_score: dict[str, float | None] = {}

    buckets: dict[str, list] = defaultdict(list)
    for sp in spans:
        label = (sp.label_ or "").strip().lower()
        if not label:
            continue
        sc = getattr(sp, "score", None)
        if sc is not None and sc < ACCEPTANCE_THRESHOLD:
            continue
        buckets[label].append(sp)

    for label, arr in buckets.items():
        arr.sort(key=lambda s: (s.end_char - s.start_char, getattr(s, "score", 0.0)), reverse=True)
        sp = arr[0]
        best_text[label] = sp.text
        best_score[label] = float(getattr(sp, "score", 0.0)) if getattr(sp, "score", None) is not None else None

    return NerCompatOut(fields=best_text, scores=best_score)

@app.get("/progress")
def progress():
    return {"status": "idle", "ready": True}

@app.post("/test-translate")
def test_translate(req: NERReq):
    """Test endpoint để kiểm tra translation mà không gọi Imagen API"""
    try:
        translated = _translate_vi_to_en(req.text)
        return {
            "original": req.text,
            "translated": translated,
            "length": len(translated),
            "status": "success"
        }
    except Exception as e:
        return {
            "original": req.text,
            "error": str(e),
            "status": "failed"
        }

@app.post("/generate", response_model=GenOut)
def generate(req: GenReq):
    print("\n--- Bắt đầu yêu cầu /generate ---")
    print(f"Prompt gốc (tiếng Việt): {req.prompt}")
    
    # 1) Translate VI->EN
    try:
        print("Bắt đầu dịch prompt...")
        prompt_en = _translate_vi_to_en(req.prompt)
        print(f"Dịch thành công. Prompt tiếng Anh: {prompt_en}")
    except Exception as e:
        print(f"!!! LỖI TRONG QUÁ TRÌNH DỊCH: {e}")
        raise HTTPException(status_code=502, detail=f"translation_error: {e}")

    # 2) Build Imagen config
    aspect = req.aspect_ratio or _guess_aspect_ratio(req.width, req.height)
    
    try:
        print("Bắt đầu tạo ảnh với Imagen...")
        img_bytes = _generate_with_imagen(
            prompt_en,
            aspect_ratio=aspect,
            number_of_images=max(1, min(4, req.number_of_images)),
            mime_type=req.mime_type,
            allow_people=req.allow_people,
        )
        print("Tạo ảnh thành công.")
    except Exception as e:
        error_msg = str(e)
        print(f"!!! LỖI TRONG QUÁ TRÌNH TẠO ẢNH: {e}")
        
        if "billed users" in error_msg or "INVALID_ARGUMENT" in error_msg:
            import io
            from PIL import Image, ImageDraw, ImageFont
            
            img = Image.new('RGB', (512, 512), color='lightgray')
            draw = ImageDraw.Draw(img)
            
            text_lines = [
                "IMAGEN API NOT AVAILABLE",
                "Billing required",
                "",
                "Translated prompt:",
                prompt_en[:100] + "..." if len(prompt_en) > 100 else prompt_en
            ]
            
            y = 50
            for line in text_lines:
                draw.text((10, y), line, fill='black')
                y += 30
            
            img_io = io.BytesIO()
            img.save(img_io, format='PNG')
            img_bytes = img_io.getvalue()
            
            print("Đã tạo ảnh placeholder thay thế.")
        else:
            raise HTTPException(status_code=502, detail=f"imagen_error: {e}")
    
    print("--- Hoàn thành yêu cầu /generate ---")
    return GenOut(image_base64=_to_data_uri(img_bytes, req.mime_type), model=f"{IMAGEN_MODEL} (fallback)" if "billed users" in str(e) else IMAGEN_MODEL)

@app.post("/interrupt")
def interrupt():
    # ....
    return {"ok": True}
