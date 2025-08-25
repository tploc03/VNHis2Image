import spacy
import json
import os

MODEL_PATH = "models/spancat_v5/model-best"
INPUT_TEXT_FOLDER = 'book_data/final_txt/Done'
OUTPUT_FOLDER = 'runs/preds_v5'
ACCEPTANCE_THRESHOLD = 0.5
SPANS_KEY = "sc"

print(f"Đang tải mô hình từ: {MODEL_PATH}")
if not os.path.exists(MODEL_PATH):
    print(f"Không tìm thấy mô hình tại '{MODEL_PATH}'.")
    exit(1)

try:
    nlp_spancat = spacy.load(MODEL_PATH)
except Exception as e:
    print(f"Lỗi khi load mô hình: {e}")
    exit(1)

if not os.path.exists(INPUT_TEXT_FOLDER):
    print(f"Thư mục đầu vào '{INPUT_TEXT_FOLDER}' không tồn tại.")
    exit(1)

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

txt_files = [f for f in os.listdir(INPUT_TEXT_FOLDER) if f.lower().endswith('.txt')]
if not txt_files:
    print(f"Không tìm thấy file .txt nào trong '{INPUT_TEXT_FOLDER}'.")
    exit(1)

for filename in txt_files:
    input_path = os.path.join(INPUT_TEXT_FOLDER, filename)
    # Đảm bảo tên file đầu ra hợp lý, loại bỏ tiền tố 'final_' nếu có
    out_name = filename.replace('final_', '').replace('.txt', '.jsonl')
    output_path = os.path.join(OUTPUT_FOLDER, out_name)

    print(f"\nĐang đọc dữ liệu từ: {input_path}")
    if not os.path.exists(input_path):
        print(f"Không tìm thấy file đầu vào '{input_path}'.")
        continue

    # Tạo file jsonl rỗng trước khi ghi
    with open(output_path, 'w', encoding='utf-8') as f:
        pass

    output_data = []
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for i, text in enumerate(lines):
        text = text.strip()
        if not text:
            continue

        doc = nlp_spancat(text)
        labels = []

        spans = doc.spans.get(SPANS_KEY, [])
        scores = getattr(spans, "attrs", {}).get("scores", [1.0]*len(spans))

        # print(f"\nCâu {i+1}: {text}")
        # if not spans:
        #     print("Không tìm thấy span nào.")

        for span, score in zip(spans, scores):
            if score >= ACCEPTANCE_THRESHOLD:
                labels.append([span.start_char, span.end_char, span.label_])

        output_data.append({'text': text, 'label': labels})

    print(f"\nĐang lưu kết quả vào: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in output_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

print("Done")