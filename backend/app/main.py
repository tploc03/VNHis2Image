# backend/app/main.py
import os, json, time
from typing import Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import spacy
import requests
from spacy.lang.vi import Vietnamese
import math

load_dotenv()
SD_URL = os.getenv("SD_WEBUI", "http://127.0.0.1:7860")
MODEL_PATH = os.getenv("MODEL_PATH", "models/spancat_v5/model-best")
SPANS_KEY = os.getenv("SPANS_KEY", "sc")
ACCEPTANCE_THRESHOLD = float(os.getenv("ACCEPTANCE_THRESHOLD", "0.3"))
SD_WEBUI = os.getenv("SD_WEBUI")  # e.g. http://127.0.0.1:7860

IMAGE_PROVIDER_DEFAULT = (os.getenv("IMAGE_PROVIDER_DEFAULT", "local") or "local").lower()
CLOUD_IMAGE_API_URL = os.getenv("CLOUD_IMAGE_API_URL") or ""
CLOUD_IMAGE_API_KEY = os.getenv("CLOUD_IMAGE_API_KEY") or ""

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = REPO_ROOT / "src" / "main" / "prompts"
TEMPLATES = json.loads((PROMPT_DIR / "prompt_templates.json").read_text(encoding="utf-8"))
SCHEMAS   = json.loads((PROMPT_DIR / "prompt_schema.json").read_text(encoding="utf-8"))

LABEL_TO_FIELD = {
    "PERSON": "person",
    "LOCATION": "location",
    "ORGANIZATION": "organization",
    "DYNASTY": "dynasty",
    "TIME": "time",
    "COSTUME": "costume",
    "ARCHITECTURE": "architecture",
    "ARTIFACT": "artifact",
    "FLORA_FAUNA": "flora_fauna",
    "EVENT": "event",
    "ACTION": "action",
    "CONCEPT": "concept",
    "TITLE": "title",
}
MULTI_FIELDS = {"artifact", "flora_fauna"}

def cloud_configured() -> bool:
    return bool(CLOUD_IMAGE_API_URL and CLOUD_IMAGE_API_KEY)

# ---------- spaCy model ----------
print(f"[NER] Loading model: {MODEL_PATH}")
nlp = spacy.load(MODEL_PATH)

try:
    # test tokenizer
    _ = nlp("xin chào")
except Exception as e:
    print("[NER] Vietnamese tokenizer lỗi PyVi:", e)
    print("[NER] Fallback sang rule-based tokenizer đơn giản.")
    nlp.tokenizer = Vietnamese().tokenizer

# ---------- FastAPI ----------
app = FastAPI(title="VNHIS2IMAGE API", version="0.2.0")

origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Schemas ----------
class NERIn(BaseModel):
    text: str
    style: str

class NEROut(BaseModel):
    fields: Dict[str, str]
    scores: Dict[str, float]
    missing: List[str] = []

class GenIn(BaseModel):
    prompt: str
    provider: Optional[str] = None  # 'local' | 'cloud' | 'auto'
    steps: Optional[int] = 30
    cfg_scale: Optional[float] = 7.0
    width: Optional[int] = 768
    height: Optional[int] = 512

class GenReq(BaseModel):
  prompt: str
  steps: int | None = 20
  width: int | None = 768
  height: int | None = 1024

class GenOut(BaseModel):
    image_url: Optional[str] = None
    image_base64: Optional[str] = None

# ---------- Helpers ----------
def validate_required(style: str, fields: Dict[str, str]) -> List[str]:
    req = SCHEMAS.get(style, {}).get("required", [])
    return [k for k in req if not fields.get(k, "").strip()]
def sd_progress(skip_current_image: bool = True) -> dict | None:
    if not SD_URL:
        return None
    try:
        r = requests.get(
            f"{SD_URL}/sdapi/v1/progress",
            params={"skip_current_image": "true" if skip_current_image else "false"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("[SD] progress error:", e)
        return None

def sd_interrupt() -> bool:
    if not SD_URL:
        return False
    try:
        r = requests.post(f"{SD_URL}/sdapi/v1/interrupt", timeout=5)
        r.raise_for_status()
        return True
    except Exception as e:
        print("[SD] interrupt error:", e)
        return False
def call_sd_webui_txt2img(prompt: str, steps=30, cfg_scale=7, width=768, height=512) -> Optional[str]:
    if not SD_WEBUI:
        return None
    try:
        r = requests.post(
            f"{SD_WEBUI}/sdapi/v1/txt2img",
            json={
                "prompt": prompt,
                "steps": steps,
                "cfg_scale": cfg_scale,
                "width": width,
                "height": height,
            },
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        if "images" in data and data["images"]:
            return f"data:image/png;base64,{data['images'][0]}"
    except Exception as e:
        print("[SD] Error:", e)
    return None

def call_cloud_txt2img(prompt: str, steps=30, cfg_scale=7, width=768, height=512) -> Optional[Dict[str,str]]:
    """
    Placeholder cloud caller.
    When CLOUD_* not configured, return None.
    Later you can implement Replicate/Stability here.
    """
    if not cloud_configured():
        return None
    try:
        headers = {"Content-Type": "application/json"}
        if CLOUD_IMAGE_API_KEY:
            headers["Authorization"] = f"Bearer {CLOUD_IMAGE_API_KEY}"
        r = requests.post(
            CLOUD_IMAGE_API_URL,
            json={
                "prompt": prompt,
                "steps": steps,
                "cfg_scale": cfg_scale,
                "width": width,
                "height": height,
            },
            headers=headers,
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("image_base64") or data.get("image_url"):
            return {"image_base64": data.get("image_base64"), "image_url": data.get("image_url")}
    except Exception as e:
        print("[CLOUD] Error:", e)
    return None
def _sd_post(path: str, json=None, timeout=5):
    try:
        r = requests.post(f"{SD_WEBUI}{path}", json=json or {}, timeout=timeout)
        r.raise_for_status()
        return True, r
    except Exception as e:
        print(f"[SD]{path} error:", e)
        return False, e

# ---------- Endpoints ----------
@app.get("/health")
def health():
    return {
        "ok": True,
        "model_path": MODEL_PATH,
        "spans_key": SPANS_KEY,
        "templates": list(TEMPLATES.keys()),
        "providers": {
            "local": bool(SD_WEBUI),
            "cloud": cloud_configured(),
            "default": IMAGE_PROVIDER_DEFAULT,
        },
    }

@app.post("/ner", response_model=NEROut)
def ner_endpoint(inp: NERIn):
    text = inp.text.strip()
    doc = nlp(text)

    spans = doc.spans.get(SPANS_KEY, [])
    scores_attr = getattr(spans, "attrs", {}).get("scores", [1.0] * len(spans))

    bucket: Dict[str, List[tuple[str, float]]] = {}
    for sp, sc in zip(spans, scores_attr):
        if sc < ACCEPTANCE_THRESHOLD:
            continue
        field = LABEL_TO_FIELD.get(sp.label_)
        if not field:
            continue
        bucket.setdefault(field, []).append((sp.text, float(sc)))

    fields: Dict[str, str] = {}
    scores: Dict[str, float] = {}

    for field, items in bucket.items():
        if field in MULTI_FIELDS:
            items_sorted = sorted(items, key=lambda x: x[1], reverse=True)
            texts = [t for t, _ in items_sorted]
            seen = set(); unique_texts = []
            for t in texts:
                if t not in seen:
                    unique_texts.append(t); seen.add(t)
            fields[field] = ", ".join(unique_texts)
            scores[field] = max(sc for _, sc in items_sorted)
        else:
            best_text, best_score = max(items, key=lambda x: x[1])
            fields[field] = best_text
            scores[field] = best_score

    for k in set(LABEL_TO_FIELD.values()):
        fields.setdefault(k, "")
        scores.setdefault(k, 0.0)

    missing = validate_required(inp.style, fields)
    return NEROut(fields=fields, scores=scores, missing=missing)

@app.post("/generate", response_model=GenOut)
def generate(req: GenReq):
    sd_base = os.getenv("SD_WEBUI", SD_WEBUI) or "http://127.0.0.1:7860"
    payload = {
        "prompt": req.prompt,
        "steps": req.steps or 30,
        "width": req.width or 768,
        "height": req.height or 1024,
        "cfg_scale": 7,
    }
    try:
        r = requests.post(f"{sd_base}/sdapi/v1/txt2img", json=payload, timeout=180)
    except requests.exceptions.RequestException as e:
        # A1111 không reachable
        raise HTTPException(status_code=502, detail=f"sd_unreachable: {e}")
    if not r.ok:
        # Trả thông tin lỗi upstream để debug
        detail = (r.text or "")[:400]
        raise HTTPException(status_code=502, detail=f"sd_bad_response_{r.status_code}: {detail}")

    j = r.json()
    img_b64 = (j.get("images") or [None])[0]
    if not img_b64:
        raise HTTPException(status_code=502, detail="sd_no_image_in_response")

    # Chuẩn hoá data URI để FE/batch đọc thống nhất
    if not img_b64.startswith("data:"):
        img_b64 = f"data:image/png;base64,{img_b64}"
    return {"image_base64": img_b64}

@app.get("/progress")
def progress():
    data = sd_progress(skip_current_image=True) or {}
    # A1111 trả { "progress": 0..1, "eta_relative": seconds, "state": {...}, "current_image": "..." }
    pct = float(data.get("progress") or 0.0)
    eta = float(data.get("eta_relative") or 0.0)
    state = data.get("state") or {}
    # Có thể thêm snapshot preview nếu muốn: current_image
    return {
        "progress": pct,                 # 0..1
        "percent": round(pct * 100, 1),  # 0..100
        "eta_seconds": int(eta),
        "job": {
            "sampling_step": state.get("sampling_step"),
            "sampling_steps": state.get("sampling_steps"),
            "job_count": state.get("job_count"),
            "job_no": state.get("job_no"),
        },
        "has_preview": bool(data.get("current_image")),
        # Nếu muốn hiển thị ảnh xem trước: bật dòng dưới, FE sẽ dùng khi cần
        # "preview_b64": data.get("current_image"),
    }

@app.post("/interrupt")
def interrupt():
    ok, r = _sd_post("/sdapi/v1/interrupt", timeout=3)
    if not ok:
        raise HTTPException(status_code=502, detail=f"interrupt_failed: {r}")
    return {"ok": True}

@app.post("/skip")
def skip():
    ok, r = _sd_post("/sdapi/v1/skip", timeout=3)
    if not ok:
        raise HTTPException(status_code=502, detail=f"skip_failed: {r}")
    return {"ok": True}
