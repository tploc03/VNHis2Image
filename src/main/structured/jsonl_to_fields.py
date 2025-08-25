import json, argparse
from collections import defaultdict
import sys
sys.stdout.reconfigure(encoding="utf-8")

# python src/main/structured/jsonl_to_fields.py --input runs/preds_all.jsonl --limit 999999 > runs/fields_all.jsonl

LABEL2FIELD = {
    "PERSON":"person","DYNASTY":"dynasty","TIME":"time","COSTUME":"costume",
    "ARCHITECTURE":"architecture","ARTIFACT":"artifact","FLORA_FAUNA":"flora_fauna",
    "EVENT":"event","ACTION":"action","CONCEPT":"concept","TITLE":"title",
    "ORGANIZATION":"organization","LOCATION":"location"
}
MULTI = {"artifact","flora_fauna"}

def line_to_fields(text, labels):
    fields = defaultdict(list)
    for s,e,lbl in labels:
        field = LABEL2FIELD.get(lbl)
        if not field: continue
        span = text[s:e]
        fields[field].append(span)
    out = {}
    for k,vals in fields.items():
        out[k] = ", ".join(dict.fromkeys(v.strip() for v in vals)) if k in MULTI else max(vals, key=len)
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="path to .jsonl")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    import io

    with open(args.input, "r", encoding="utf-8") as f, \
        open("runs/fields_all.jsonl", "w", encoding="utf-8") as out:
        for i, line in enumerate(f, 1):
            if i > args.limit:
                break
            obj = json.loads(line)
            fields = line_to_fields(obj["text"], obj.get("label", []))
            out.write(json.dumps({"text": obj["text"], "fields": fields}, ensure_ascii=False) + "\n")

