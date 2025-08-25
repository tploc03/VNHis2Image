import json, argparse, re
from pathlib import Path

# Load templates & schema from repo
TEMPLATES = json.loads(Path("src/main/prompts/prompt_templates.json").read_text(encoding="utf-8"))
SCHEMAS   = json.loads(Path("src/main/prompts/prompt_schema.json").read_text(encoding="utf-8"))

# Usage:
# python src/main/prompts/batch_render_prompts.py --input runs/fields_all.jsonl --style portrait --out runs/prompts/portrait.jsonl

PLACEHOLDER_RE = re.compile(r"\[([a-zA-Z0-9_]+)\]")

def extract_placeholders(t: str):
    return list({m.group(1) for m in PLACEHOLDER_RE.finditer(t)})

def render(style, fields, extra=""):
    temp = TEMPLATES[style]
    holes = extract_placeholders(temp)
    required = set(SCHEMAS.get(style, {}).get("required", []))

    missing = [h for h in required if not fields.get(h)]
    if missing:
        raise ValueError(f"Thiếu bắt buộc: {', '.join(missing)}")

    for h in holes:
        val = fields.get(h, "") or ""
        temp = temp.replace(f"[{h}]", val)

    if extra.strip():
        temp += f"\nAdditional notes: {extra.strip()}\n"
    temp += "\nLanguage: Vietnamese.\n"
    return temp.strip()

def fields_from_obj(obj):
    if "fields" in obj and isinstance(obj["fields"], dict):
        return obj["fields"]
    from ..structured.jsonl_to_fields import line_to_fields  # lazy import
    return line_to_fields(obj["text"], obj.get("label", []))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="JSONL: {text,fields} hoặc {text,label}")
    ap.add_argument("--style", required=True, choices=list(TEMPLATES.keys()))
    ap.add_argument("--out", default="runs/prompts.jsonl")
    args = ap.parse_args()

    Path("runs/prompts").mkdir(parents=True, exist_ok=True)

    kept = skipped = 0
    with open(args.input, "r", encoding="utf-8") as f, open(args.out, "w", encoding="utf-8") as w:
        for line in f:
            obj = json.loads(line)
            try:
                flds = fields_from_obj(obj)
                p = render(args.style, flds)
                w.write(json.dumps({"prompt": p, "fields": flds}, ensure_ascii=False) + "\n")
                kept += 1
            except Exception:
                skipped += 1

    print(f"Done -> {args.out} | kept={kept}, skipped={skipped}")

if __name__ == "__main__":
    main()
