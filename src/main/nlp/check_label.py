import json
from collections import defaultdict, Counter
import re

def analyze_label_consistency(jsonl_file_path, show_examples=True, max_examples=5, output_file=None):
    """
    Phân tích file JSONL từ Doccano để kiểm tra sự nhất quán trong việc gán nhãn.

    Args:
        jsonl_file_path (str): Đường dẫn đến file .jsonl cần phân tích.
        show_examples (bool): Có hiển thị ví dụ câu chứa thực thể không nhất quán không.
        max_examples (int): Số lượng ví dụ tối đa hiển thị cho mỗi thực thể.
        output_file (str): Đường dẫn file để ghi kết quả. Nếu None sẽ tự động tạo.
    """
    # Tự động tạo tên file output nếu không được cung cấp
    if output_file is None:
        import os
        base_name = os.path.splitext(os.path.basename(jsonl_file_path))[0]
        output_file = f"label_analysis_{base_name}.txt"
    
    # Tạo buffer để ghi output
    output_lines = []
    
    def write_output(text, print_also=True):
        """Helper function để vừa ghi file vừa in console"""
        output_lines.append(text)
        if print_also:
            print(text)
    # Dùng defaultdict để dễ dàng thống kê
    label_counts = defaultdict(int)
    entity_labels = defaultdict(lambda: defaultdict(list))  # Lưu cả thông tin vị trí và câu
    entity_positions = defaultdict(list)  # Lưu vị trí xuất hiện của thực thể
    
    total_lines = 0
    total_entities = 0
    sentences = []  # Lưu tất cả câu để có thể tham chiếu sau

    write_output(f"--- Bắt đầu phân tích file: {jsonl_file_path} ---")

    try:
        with open(jsonl_file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                total_lines += 1
                data = json.loads(line)
                text = data['text']
                labels = data.get('label', [])
                sentences.append(text)
                
                for start, end, label_name in labels:
                    entity_text = text[start:end].strip().lower()
                    original_entity = text[start:end]  # Giữ nguyên để hiển thị
                    
                    # Đếm tổng số lần xuất hiện của mỗi nhãn
                    label_counts[label_name] += 1
                    total_entities += 1
                    
                    # Ghi nhận thông tin chi tiết về thực thể
                    entity_info = {
                        'line_num': line_num,
                        'original_text': original_entity,
                        'sentence': text,
                        'start': start,
                        'end': end
                    }
                    entity_labels[entity_text][label_name].append(entity_info)
                    entity_positions[entity_text].append((line_num, label_name, original_entity))

    except FileNotFoundError:
        error_msg = f"Lỗi: Không tìm thấy file tại '{jsonl_file_path}'"
        write_output(error_msg)
        return
    except json.JSONDecodeError as e:
        error_msg = f"Lỗi: File JSONL không hợp lệ ở dòng {total_lines + 1}. Lỗi: {e}"
        write_output(error_msg)
        return

    write_output("\n1. TỔNG QUAN PHÂN PHỐI NHÃN")
    write_output(f"Tổng số câu: {total_lines}")
    write_output(f"Tổng số thực thể đã gán nhãn: {total_entities}\n")
    
    # Sắp xếp các nhãn theo số lượng giảm dần
    sorted_labels = sorted(label_counts.items(), key=lambda item: item[1], reverse=True)
    
    write_output(f"{'NHÃN':<25} | {'SỐ LƯỢNG':<10} | {'TỶ LỆ %':<8}")
    for label, count in sorted_labels:
        percentage = (count / total_entities) * 100
        write_output(f"{label:<25} | {count:<10} | {percentage:>6.1f}%")

    write_output("\n2. PHÂN TÍCH CÁC THỰC THỂ KHÔNG NHẤT QUÁN")
    write_output("(Các thực thể được gán nhiều hơn 1 loại nhãn khác nhau)\n")
    
    inconsistent_entities = []
    for entity, labels in entity_labels.items():
        if len(labels) > 1:
            inconsistent_entities.append((entity, labels))
    
    if not inconsistent_entities:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        print(f"\nKết quả đã được ghi vào file: {output_file}")
        return
    
    # Sắp xếp theo số lượng nhãn khác nhau (nhiều nhất trước)
    inconsistent_entities.sort(key=lambda x: len(x[1]), reverse=True)
    
    write_output(f"Tìm thấy {len(inconsistent_entities)} thực thể không nhất quán:\n")
    
    for i, (entity, labels) in enumerate(inconsistent_entities, 1):
        write_output(f"{i}. Thực thể: '{entity}'")
        write_output(f"Số nhãn khác nhau: {len(labels)}")
        
        # Hiển thị thống kê các nhãn
        for label, occurrences in labels.items():
            write_output(f"   -> Nhãn '{label}': {len(occurrences)} lần")
        
        if show_examples:
            # Tìm nhãn xuất hiện nhiều nhất (có thể coi là "đúng")
            label_counts_for_entity = {label: len(occurrences) for label, occurrences in labels.items()}
            max_count = max(label_counts_for_entity.values())
            
            # Chỉ hiển thị các nhãn "bất thường" (không phải nhãn xuất hiện nhiều nhất)
            minority_labels = {label: occurrences for label, occurrences in labels.items() 
                             if len(occurrences) < max_count}
            
            if minority_labels:
                write_output(" Ví dụ vị trí xuất hiện bất thường (cần xem lại):")
                example_count = 0
                
                for label, occurrences in minority_labels.items():
                    if example_count >= max_examples:
                        remaining = sum(len(occ) for occ in minority_labels.values()) - example_count
                        if remaining > 0:
                            write_output(f"      ... và {remaining} ví dụ khác cần xem lại")
                        break
                        
                    for occurrence in occurrences:
                        if example_count >= max_examples:
                            break
                        
                        line_num = occurrence['line_num']
                        sentence = occurrence['sentence']
                        original_text = occurrence['original_text']
                        
                        # Làm nổi bật thực thể trong câu
                        highlighted_sentence = sentence.replace(
                            original_text, 
                            f"**{original_text}**"
                        )
                        
                        write_output(f"      • Dòng {line_num}, nhãn '{label}' (bất thường): {highlighted_sentence}")
                        example_count += 1
                
                # Thông báo nhãn chính thống để tham khảo
                main_labels = [label for label, occurrences in labels.items() 
                             if len(occurrences) == max_count]
                write_output(f"   Nhãn có vẻ đúng: {', '.join(main_labels)} ({max_count} lần)")
            else:
                write_output("   Tất cả nhãn đều xuất hiện với tần suất bằng nhau")
        
        write_output("-" * 80)
    
    write_output(f"\nTHỐNG KÊ TỔNG KẾT:")
    write_output(f"Tổng thực thể không nhất quán: {len(inconsistent_entities)}")
    write_output(f"Tỷ lệ thực thể không nhất quán: {len(inconsistent_entities)/len(entity_labels)*100:.1f}%")
    
    # Thêm phân tích về các cặp nhãn thường bị nhầm lẫn
    write_output(f"\n3. CÁC CẶP NHÃN THƯỜNG BỊ NHẦM LẪN")
    label_conflicts = defaultdict(int)
    
    for entity, labels in inconsistent_entities:
        label_names = list(labels.keys())
        if len(label_names) == 2:  # Chỉ xét trường hợp 2 nhãn để đơn giản
            pair = tuple(sorted(label_names))
            label_conflicts[pair] += 1
    
    if label_conflicts:
        sorted_conflicts = sorted(label_conflicts.items(), key=lambda x: x[1], reverse=True)
        for (label1, label2), count in sorted_conflicts:
            write_output(f"   • '{label1}' ↔ '{label2}': {count} thực thể")
    else:
        write_output("Không có cặp nhãn nào bị nhầm lẫn đặc biệt.")
    
    # Ghi tất cả output vào file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        print(f"\nKết quả chi tiết đã được ghi vào file: {output_file}")
    except Exception as e:
        print(f"\nLỗi khi ghi file: {e}")

def find_similar_entities(jsonl_file_path, similarity_threshold=0.8, output_file=None):
    """
    Tìm các thực thể tương tự nhau có thể bị gán nhãn khác nhau.
    Hữu ích để phát hiện lỗi chính tả hoặc biến thể của cùng một thực thể.
    """
    from difflib import SequenceMatcher
    
    # Tạo tên file output cho function này
    if output_file is None:
        import os
        base_name = os.path.splitext(os.path.basename(jsonl_file_path))[0]
        output_file = f"similar_entities_{base_name}.txt"
    
    output_lines = []
    
    def write_output(text, print_also=True):
        output_lines.append(text)
        if print_also:
            print(text)
    
    entity_labels = defaultdict(set)
    
    try:
        with open(jsonl_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                text = data['text']
                labels = data.get('label', [])
                
                for start, end, label_name in labels:
                    entity_text = text[start:end].strip().lower()
                    entity_labels[entity_text].add(label_name)
    
    except Exception as e:
        error_msg = f"Lỗi khi đọc file: {e}"
        write_output(error_msg)
        return
    
    write_output(f"\n--- 4. THỰC THỂ TƯƠNG TỰ CÓ NHÃN KHÁC NHAU ---")
    write_output(f"(Độ tương tự >= {similarity_threshold*100:.0f}%)\n")
    
    entities = list(entity_labels.keys())
    similar_pairs = []
    
    for i, entity1 in enumerate(entities):
        for j, entity2 in enumerate(entities[i+1:], i+1):
            similarity = SequenceMatcher(None, entity1, entity2).ratio()
            if similarity >= similarity_threshold and entity_labels[entity1] != entity_labels[entity2]:
                similar_pairs.append((entity1, entity2, similarity, 
                                    entity_labels[entity1], entity_labels[entity2]))
    
    if similar_pairs:
        similar_pairs.sort(key=lambda x: x[2], reverse=True)
        for entity1, entity2, similarity, labels1, labels2 in similar_pairs:
            write_output(f"Độ tương tự: {similarity:.1%}")
            write_output(f"   '{entity1}' → {', '.join(labels1)}")
            write_output(f"   '{entity2}' → {', '.join(labels2)}")
    else:
        write_output("Không tìm thấy thực thể tương tự nào có nhãn khác nhau.")
    
    # Ghi file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        print(f"\nKết quả thực thể tương tự đã được ghi vào file: {output_file}")
    except Exception as e:
        print(f"\nLỗi khi ghi file: {e}")

if __name__ == '__main__':
    # Thay đổi đường dẫn này thành đường dẫn đến file jsonl của bạn
    file_path = 'book_data/labeled/json_files/v4/v4.jsonl'
    
    # Phân tích cơ bản - sẽ tự động tạo file output
    # analyze_label_consistency(
    #     file_path, 
    #     show_examples=True, 
    #     max_examples=3,
    #     output_file=None
    # )
    
    # Hoặc chỉ định tên file cụ thể
    analyze_label_consistency(
        file_path, 
        show_examples=True, 
        max_examples=5,
        output_file="report.txt"
    )
    
    # Phân tích thực thể tương tự (tùy chọn) - cũng sẽ ghi ra file riêng
    # find_similar_entities(file_path, similarity_threshold=0.8)