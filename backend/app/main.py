# backend/app/main.py
# -*- coding: utf-8 -*-
"""
FastAPI backend — Generate images with Google Gemini Imagen 3
Workflow (ẩn trong hệ thống):
1) Nhận prompt (VI) từ người dùng
2) Dịch sang EN bằng Gemini (TRANSLATE_MODEL)
3) Gọi Imagen 3 (IMAGEN_MODEL) để sinh ảnh
"""
from __future__ import annotations

import os
import base64
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from google import genai
from google.genai import types
from dotenv import load_dotenv


load_dotenv()


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
IMAGEN_MODEL = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
TRANSLATE_MODEL = os.getenv("TRANSLATE_MODEL", "gemini-2.5-pro")
IMAGEN_SAMPLE_SIZE = os.getenv("IMAGEN_SAMPLE_SIZE", "1K")
ALLOW_PEOPLE = os.getenv("ALLOW_PEOPLE", "allow_adult")
DEFAULT_MIME = os.getenv("IMAGEN_MIME", "image/png")
DEFAULT_NUM_IMAGES = int(os.getenv("IMAGEN_NUM_IMAGES", "1"))

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "*")
ALLOWED_METHODS = os.getenv("ALLOWED_METHODS", "GET,POST,OPTIONS")
ALLOWED_HEADERS = os.getenv("ALLOWED_HEADERS", "*")


if not GOOGLE_API_KEY:
    pass

client = genai.Client()

app = FastAPI(title="Historical Image Generator (Gemini Imagen 3)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS.split(",")] if ALLOWED_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=[m.strip() for m in ALLOWED_METHODS.split(",")] if ALLOWED_METHODS else ["*"],
    allow_headers=[h.strip() for h in ALLOWED_HEADERS.split(",")] if ALLOWED_HEADERS else ["*"],
)

AspectRatioT = Literal["1:1", "3:4", "4:3", "9:16", "16:9"]
SampleSizeT = Literal["1K", "2K"]
PeopleT = Literal["dont_allow", "allow_adult", "allow_all"]


class GenReq(BaseModel):
    prompt: str = Field(..., description="Prompt tiếng Việt hoặc prompt từ form.")
    aspect_ratio: Optional[AspectRatioT] = Field(None, description="Aspect ratio cho Imagen.")
    sample_image_size: Optional[SampleSizeT] = Field(None, description='Kích cỡ mẫu "1K" hoặc "2K"')
    number_of_images: int = Field(DEFAULT_NUM_IMAGES, ge=1, le=4, description="Số ảnh muốn sinh (1-4).")
    mime_type: Literal["image/png", "image/jpeg"] = Field(DEFAULT_MIME, description="Định dạng ảnh output.")
    allow_people: PeopleT = Field(ALLOW_PEOPLE, description="Chính sách sinh ảnh có người.")
    width: Optional[int] = None
    height: Optional[int] = None


class GenOut(BaseModel):
    image_base64: str
    model: str = Field(..., description="Model Imagen dùng để sinh.")


def _guess_aspect_ratio(width: Optional[int], height: Optional[int]) -> AspectRatioT:
    """
    Chuyển width/height (nếu được gửi) sang aspect_ratio hợp lệ của Imagen.
    Nếu không có, trả mặc định "1:1".
    """
    if not width or not height or width <= 0 or height <= 0:
        return "1:1"
    r = width / float(height)
    ratios = {
        "1:1": 1.0,
        "3:4": 0.75,
        "4:3": 1.3333,
        "9:16": 0.5625,
        "16:9": 1.7777,
    }
    best = min(ratios.items(), key=lambda kv: abs(kv[1] - r))[0]
    return best  # type: ignore[return-value]


def _to_data_uri(image_bytes: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"


def _translate_vi_to_en(vietnamese_prompt: str) -> str:
    """
    Dịch prompt sang tiếng Anh bằng Gemini (TRANSLATE_MODEL).
    Lưu ý: Imagen chỉ hỗ trợ prompt tiếng Anh. (docs)  # noqa
    """
    if not vietnamese_prompt or not vietnamese_prompt.strip():
        raise ValueError("empty_prompt")

    cfg = types.GenerateContentConfig(
        system_instruction=(
            "You are a professional translator for visual art prompts. "
            "Translate the user's Vietnamese text into concise, natural English "
            "for image generation. Keep proper nouns (Vietnamese dynasties, "
            "names, places) accurately romanized. Do NOT add new details. "
            "Return ONLY the English prompt text."
        ),
        temperature=0.2,
        max_output_tokens=300,
    )

    resp = client.models.generate_content(
        model=TRANSLATE_MODEL,
        contents=vietnamese_prompt,
        config=cfg,
    )
    text = (resp.text or "").strip()
    if text.startswith("```"):
        text = text.strip("` \n")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) >= 2:
            text = "\n".join(lines[1:])
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()

    if not text:
        raise RuntimeError("translation_failed")
    return text


def _generate_with_imagen(
    prompt_en: str,
    *,
    aspect_ratio: AspectRatioT,
    sample_image_size: SampleSizeT,
    number_of_images: int,
    mime_type: str,
    allow_people: PeopleT,
) -> bytes:
    """
    Gọi Imagen 3 để sinh ảnh; trả về bytes của ảnh đầu tiên.
    """
    cfg = types.GenerateImagesConfig(
        number_of_images=number_of_images,
        sample_image_size=sample_image_size,
        aspect_ratio=aspect_ratio,
        person_generation=allow_people,
        include_rai_reason=True,
        output_mime_type=mime_type,
    )

    resp = client.models.generate_images(
        model=IMAGEN_MODEL,
        prompt=prompt_en,
        config=cfg,
    )

    if not resp.generated_images:
        raise RuntimeError("no_image_generated")

    img_obj = resp.generated_images[0].image
    image_bytes: Optional[bytes] = getattr(img_obj, "image_bytes", None)

    if image_bytes is None:
        image_bytes = getattr(img_obj, "bytes", None) or getattr(img_obj, "data", None)

    if not image_bytes or not isinstance(image_bytes, (bytes, bytearray)):
        raise RuntimeError("image_bytes_missing")

    return bytes(image_bytes)

@app.get("/health")
def health():
    return {
        "ok": True,
        "imagen_model": IMAGEN_MODEL,
        "translate_model": TRANSLATE_MODEL,
        "supports": {
            "aspect_ratio": ["1:1", "3:4", "4:3", "9:16", "16:9"],
            "sample_image_size": ["1K", "2K"],
            "mime": ["image/png", "image/jpeg"],
        },
        "notes": "Prompts are auto-translated VI→EN before Imagen generation.",
    }


@app.post("/generate", response_model=GenOut)
def generate(req: GenReq):
    if not GOOGLE_API_KEY:
        raise HTTPException(status_code=401, detail="missing_GOOGLE_API_KEY")

    # 1) Hidden step: Translate VI -> EN
    try:
        prompt_en = _translate_vi_to_en(req.prompt)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"translation_error: {e}")

    # 2) Build Imagen config
    aspect = req.aspect_ratio or _guess_aspect_ratio(req.width, req.height)
    sample_size = req.sample_image_size or IMAGEN_SAMPLE_SIZE
    try:
        img_bytes = _generate_with_imagen(
            prompt_en,
            aspect_ratio=aspect,
            sample_image_size=sample_size,  # Only for Standard/Ultra; safe default
            number_of_images=max(1, min(4, req.number_of_images)),
            mime_type=req.mime_type,
            allow_people=req.allow_people,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"imagen_error: {e}")

    return GenOut(
        image_base64=_to_data_uri(img_bytes, req.mime_type),
        model=IMAGEN_MODEL,
    )


@app.get("/")
def root():
    return {"message": "Historical Image Generator API (Gemini Imagen 3). Use POST /generate."}
