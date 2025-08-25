import spacy
import json

MODEL_PATH = "models/ner_v4/model-best"
INPUT_JSONL_FILE = "book_data/labeled/json_files/v3/lamsonthucluc_trangphuc_danhlam_1334_vnsl.jsonl"
OUTPUT_JSONL_FILE = "book_data/labeled/json_files/v4/lamsonthucluc_trangphuc_danhlam_vnsl-v4.jsonl"

ACCEPTANCE_THRESHOLD = 0.5
SPANS_KEY = "sc"

print(f"Đang tải mô hình từ: {MODEL_PATH}")
try:
    nlp_spancat = spacy.load(MODEL_PATH)
except IOError:
    print(f"Không tìm thấy mô hình tại '{MODEL_PATH}'.")
    exit()

print(f"Đang đọc dữ liệu từ: {INPUT_JSONL_FILE}")
try:
    with open(INPUT_JSONL_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
except FileNotFoundError:
    print(f"Không tìm thấy file đầu vào '{INPUT_JSONL_FILE}'.")
    exit()

output_data = []
for i, line in enumerate(lines):
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        print(f"Lỗi JSON ở dòng {i+1}, bỏ qua.")
        continue

    text = obj.get("text", "").strip()
    if not text:
        obj["label"] = obj.get("label", [])
        output_data.append(obj)
        continue

    doc = nlp_spancat(text)
    labels = obj.get("label", [])

    existing = set(tuple(l) for l in labels)

    spans = doc.spans.get(SPANS_KEY, [])
    scores = getattr(spans, "attrs", {}).get("scores", [1.0]*len(spans))

    print(f"\nDòng {i+1}: {text}")
    if not spans:
        print("Không tìm thấy span nào.")

    for span, score in zip(spans, scores):
        new_label = (span.start_char, span.end_char, span.label_)
        print(f"Tìm thấy: '{span.text}' ({span.label_}) - Điểm: {score:.2f}")
        if score >= ACCEPTANCE_THRESHOLD and new_label not in existing:
            labels.append(list(new_label))
            existing.add(new_label)

    obj["label"] = labels
    output_data.append(obj)

print(f"\nĐang lưu kết quả vào: {OUTPUT_JSONL_FILE}")
with open(OUTPUT_JSONL_FILE, 'w', encoding='utf-8') as f:
    for item in output_data:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')

print("Done")