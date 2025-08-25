import random
import json
import os

random.seed(2025)
input_file = "data/labeled/json_files/v4/v4.jsonl"
output_dir = "data/labeled/json_files/v5"
train_ratio = 0.8

os.makedirs(output_dir, exist_ok=True)

print(f"Đang đọc dữ liệu từ: {input_file}")

if not os.path.exists(input_file):
    print(f"Lỗi: File {input_file} không tồn tại!")
    exit(1)

data = []
errors = 0

with open(input_file, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        try:
            obj = json.loads(line.strip())
            data.append(obj)
        except json.JSONDecodeError as e:
            errors += 1
            print(f"Lỗi JSON ở dòng {line_num}: {e}")

if errors > 0:
    print(f"Có {errors} dòng lỗi được bỏ qua")

if len(data) == 0:
    print("Không có dữ liệu hợp lệ để xử lý!")
    exit(1)

print(f"Tổng số mẫu hợp lệ: {len(data)}")

random.shuffle(data)

split_point = int(train_ratio * len(data))
train_data = data[:split_point]
dev_data = data[split_point:]

print(f"Train set: {len(train_data)} mẫu ({len(train_data)/len(data)*100:.1f}%)")
print(f"Dev set: {len(dev_data)} mẫu ({len(dev_data)/len(data)*100:.1f}%)")

train_file = os.path.join(output_dir, "train.jsonl")
with open(train_file, "w", encoding="utf-8") as f:
    for item in train_data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
print(f"Đã ghi train set: {train_file}")

dev_file = os.path.join(output_dir, "dev.jsonl")
with open(dev_file, "w", encoding="utf-8") as f:
    for item in dev_data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
print(f"Đã ghi dev set: {dev_file}")

if data and 'label' in data[0]:
    def count_labels(dataset, name):
        label_counts = {}
        for item in dataset:
            labels = item.get('label', [])
            if labels:
                for label_info in labels:
                    if isinstance(label_info, list) and len(label_info) >= 3:
                        label_type = label_info[2]
                        label_counts[label_type] = label_counts.get(label_type, 0) + 1
        
        print(f"\nPhân bố nhãn trong {name}:")
        for label, count in sorted(label_counts.items()):
            print(f"  {label}: {count}")
        return label_counts
    
    train_labels = count_labels(train_data, "train set")
    dev_labels = count_labels(dev_data, "dev set")

print(f"\nHoàn thành! Random seed: {2025}")