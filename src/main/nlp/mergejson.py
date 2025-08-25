import os
import glob

input_folder = "runs/preds_v5"
output = "runs/preds_all.jsonl"

# Tạo thư mục output nếu chưa có
os.makedirs(os.path.dirname(output), exist_ok=True)

total_lines = 0
errors = 0

with open(output, 'w', encoding='utf-8') as out:
    for fname in glob.glob(os.path.join(input_folder, "*.jsonl")):
        print(f"Đang nối file: {fname}")
        with open(fname, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    # chỉ ghi nguyên dòng, không kiểm tra trùng
                    out.write(line)
                    total_lines += 1
                except Exception as e:
                    errors += 1
                    print(f"Lỗi khi ghi dòng {line_num} trong {fname}: {e}")

print(f"\nKết quả:")
print(f"- Tổng số dòng đã nối: {total_lines}")
print(f"- Số dòng lỗi: {errors}")
print(f"- File output: {output}")
