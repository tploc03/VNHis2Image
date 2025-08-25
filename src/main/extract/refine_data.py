import os
import re
from pathlib import Path
from underthesea import sent_tokenize, word_tokenize
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List

RE_METADATA = re.compile(r'\[.*?\]')
RE_SINGLE_CHAR = re.compile(r'\b([a-zA-ZÀ-ỹ])\s(?=[a-zA-ZÀ-ỹ]\b)')

def process_single_file(input_file: Path, output_folder: Path):
    try:
        content = input_file.read_text(encoding='utf-8')

        content = RE_METADATA.sub('', content)
        
        content = RE_SINGLE_CHAR.sub(r'\1', content)

        sentences = sent_tokenize(content)
        
        final_processed_lines = []
        
        for sentence in sentences:
            cleaned_sentence = sentence.strip()
            if not cleaned_sentence:
                continue
            
            tokens = word_tokenize(cleaned_sentence)
            
            processed_tokens = [token.replace('_', ' ') for token in tokens]
            
            final_line = ' '.join(processed_tokens)
            final_processed_lines.append(final_line)

        # output_filename = f"final_{input_file.name.replace('cleaned_', '')}"
        output_filename = f"{input_file.name}"
        output_path = output_folder / output_filename
        
        output_path.write_text('\n'.join(final_processed_lines), encoding='utf-8')
        
        return input_file.name

    except Exception as e:
        print(f"Error '{input_file.name}': {e}")
        return None

def main_parallel_processing(input_folder: str, output_folder: str, max_workers: int = None):
    input_path = Path(input_folder)
    output_path = Path(output_folder)

    output_path.mkdir(exist_ok=True)

    if not input_path.is_dir():
        print(f"Could not find '{input_folder}'")
        return

    files_to_process = list(input_path.glob('*.txt'))
    
    if not files_to_process:
        print(f"Could not find any .txt files in '{input_folder}'")
        return

    print(f"Found {len(files_to_process)} files to process.")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_single_file, file_path, output_path) for file_path in files_to_process]
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                print(f"Done: {result}")

    print(f"\nDone {len(files_to_process)} files.")

if __name__ == '__main__':
    input_directory = 'book_data/final_txt/Done'
    output_directory = 'book_data/final_txt/Done'
    
    main_parallel_processing(input_directory, output_directory)
