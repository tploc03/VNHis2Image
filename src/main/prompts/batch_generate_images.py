import os, json, base64, argparse, hashlib, time, urllib.parse, mimetypes
from pathlib import Path
import requests
from dotenv import load_dotenv
import base64, re

load_dotenv()

def _setup_gemini():
    try:
        import google.generativeai as genai
    except Exception as e:
        return None, f"google-generativeai not available: {e}"
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None, "Missing GEMINI_API_KEY"
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-pro")
        return model, None
    except Exception as e:
        return None, f"Gemini init error: {e}"

def _translate_vi2en(text: str, model) -> str:
    if not text or not model:
        return text
    try:
        prompt = (
            "Translate the following Vietnamese text to precise English for an image generation prompt. "
            "Keep proper nouns (people, dynasties, places) faithfully transliterated; do not summarize or add content. "
            "Preserve list structure and punctuation. Output English only.\n\n"
            f"Vietnamese:\n{text}"
        )
        resp = model.generate_content(prompt)
        out = (getattr(resp, "text", None) or "").strip()
        return out or text
    except Exception:
        return text

# ---------- Helpers ----------
def _parse_data_uri(uri: str):
    assert uri.startswith("data:")
    header, payload = uri.split(",", 1)
    header = header[len("data:"):]
    parts = header.split(";")
    mime = parts[0] if parts else "application/octet-stream"
    is_base64 = any(p.lower() == "base64" for p in parts[1:])
    return mime, is_base64, payload

def _pick_ext_from_mime(mime: str, default: str = ".png"):
    ext = mimetypes.guess_extension(mime) or default
    if mime.startswith("image/svg"): ext = ".svg"
    if mime == "image/jpeg": ext = ".jpg"
    return ext

def _fix_b64(s: str) -> str:
    s = s.strip()
    if s.startswith("data:"):
        s = s.split(",", 1)[-1]
    s = re.sub(r"\s+", "", s)
    s += "=" * (-len(s) % 4)
    return s

def save_image_from_response(resp_obj, out_dir: Path, idx: int, prompt_text: str):
    image_url = resp_obj.get("image_url")
    image_b64 = resp_obj.get("image_base64")
    h = hashlib.sha1(prompt_text.encode("utf-8")).hexdigest()[:10]

    # 1) Base64 trả về từ backend (/generate hiện trả images[0] không kèm 'data:')
    if image_b64:
        if image_b64.startswith("data:"):
            mime, is_b64, payload = _parse_data_uri(image_b64)
            ext = _pick_ext_from_mime(mime, ".png")
            out_path = out_dir / f"{idx:05d}_{h}{ext}"
            with open(out_path, "wb") as f:
                if is_b64:
                    f.write(base64.b64decode(_fix_b64(payload), validate=False))
                else:
                    f.write(urllib.parse.unquote_to_bytes(payload))
            return str(out_path)
        else:
            # KHÔNG có prefix -> vá padding rồi decode
            out_path = out_dir / f"{idx:05d}_{h}.png"
            fixed = _fix_b64(image_b64)
            with open(out_path, "wb") as f:
                f.write(base64.b64decode(fixed, validate=False))
            return str(out_path)

    # 2) URL ảnh
    if image_url:
        if image_url.startswith("data:"):
            mime, is_b64, payload = _parse_data_uri(image_url)
            ext = _pick_ext_from_mime(mime, ".png")
            out_path = out_dir / f"{idx:05d}_{h}{ext}"
            with open(out_path, "wb") as f:
                if is_b64:
                    f.write(base64.b64decode(_fix_b64(payload), validate=False))
                else:
                    f.write(urllib.parse.unquote_to_bytes(payload))
            return str(out_path)
        else:
            # Tải qua HTTP bình thường (đúng với URL)
            r = requests.get(image_url, timeout=60)
            r.raise_for_status()
            ctype = r.headers.get("Content-Type", "image/png")
            ext = _pick_ext_from_mime(ctype, ".png")
            out_path = out_dir / f"{idx:05d}_{h}{ext}"
            with open(out_path, "wb") as f:
                f.write(r.content)
            return str(out_path)

    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", required=True, help="prompts.jsonl (mỗi dòng: {prompt: ..., fields: {...}})")
    ap.add_argument("--api_base", default="http://127.0.0.1:8001")
    ap.add_argument("--out_dir", default="runs/images")
    ap.add_argument("--sleep", type=float, default=0.0)
    ap.add_argument("--translate", action="store_true", help="Translate VI->EN via Gemini before sending to backend")
    ap.add_argument("--provider", choices=["auto", "local", "cloud"], default="auto",
                    help="Hint provider for backend /generate (auto|local|cloud)")
    args = ap.parse_args()

    api_gen = args.api_base.rstrip("/") + "/generate"
    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    model = None
    if args.translate:
        model, err = _setup_gemini()
        if err:
            print(f"[WARN] Translation disabled: {err}")

    ok, fail = 0, 0
    with open(args.prompts, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            obj = json.loads(line)
            vi_prompt = (obj.get("prompt") or "").strip()
            if not vi_prompt:
                print(f"[ERR] line {i}: missing 'prompt' in input JSONL")
                fail += 1; continue

            final_prompt = _translate_vi2en(vi_prompt, model) if model else vi_prompt

            payload = {"prompt": final_prompt}
            if args.provider:
                payload["provider"] = args.provider

            try:
                r = requests.post(api_gen, json=payload, timeout=180)
                if r.status_code == 503:
                    print(f"[WARN] line {i}: cloud provider not configured on server (HTTP 503).")
                    fail += 1
                    continue
                r.raise_for_status()
                data = r.json()
                saved = save_image_from_response(data, out_dir, i, final_prompt)
                if saved:
                    ok += 1
                else:
                    print(f"[ERR] line {i}: response missing image_url/base64")
                    fail += 1
            except requests.HTTPError as e:
                try:
                    msg = r.text[:300]
                except Exception:
                    msg = str(e)
                print(f"[ERR] line {i}: HTTP {getattr(r, 'status_code', '?')} - {msg}")
                fail += 1
            except Exception as e:
                print(f"[ERR] line {i}: {e}")
                fail += 1

            if args.sleep > 0:
                time.sleep(args.sleep)

    print(f"Done. Saved: {ok}, Failed: {fail}, Out: {out_dir}")

if __name__ == "__main__":
    main()
