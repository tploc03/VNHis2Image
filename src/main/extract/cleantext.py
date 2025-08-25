import os
import re

def clean_text(text):
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    
    text = re.sub(r'(\S)-\s*\n\s*(\S)', r'\1\2', text)
    
    text = re.sub(r'---\s*Trang\s*\d+\s*---', '', text, flags=re.IGNORECASE)
    text = re.sub(r'---\s*trang\s*\d+\s*--\d*', '', text, flags=re.IGNORECASE)
    
    text = re.sub(r'([A-ZÁÀẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-záàảãạăằắẳẵặâầấẩẫậèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+)\s*\n\s*([A-ZÁÀẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-záàảãạăằắẳẵặâầấẩẫậèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+)', r'\1 \2', text)
    
    text = re.sub(r'(\d{4})\s*-\s*(\d{4})', r'\1-\2', text)
    
    text = re.sub(r'^\s*\d{1,3}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[IVXLCDM]{1,4}\s*$', '', text, flags=re.MULTILINE)
    
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    text = re.sub(r'[•◆►★☆▪▫■□●○◦‣⁃]+', '', text)
    
    text = re.sub(r'[^\w\s.,!?;:\-\(\)\'\"–—\nàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễ'
              r'ìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
              r'ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄ'
              r'ÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮ'
              r'ỲÝỴỶỸĐ\[\]/]', '', text)
    
    text = re.sub(r'(?<![.?!:])\n(?!\n)', ' ', text)
    
    text = re.sub(r'([.,!?;:])(\w)', r'\1 \2', text) 
    text = re.sub(r'(\w)\s+([.,!?;:])', r'\1\2', text)
    
    text = re.sub(r'\b([a-záàảãạăằắẳẵặâầấẩẫậèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ])\s+([a-záàảãạăằắẳẵặâầấẩẫậèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ])\b', r'\1\2', text)
    
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    text = re.sub(r'([.,!?;:])\s+', r'\1 ', text)
    
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = '\n'.join(lines)
    
    text = text.lower()
    
    text = re.sub(r' +', ' ', text)
    
    return text.strip()

def process_all_texts(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    for filename in os.listdir(input_folder):
        if filename.endswith('.txt'):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, f'cleaned_{filename}')
            
            with open(input_path, 'r', encoding='utf-8', errors='replace') as f:
                raw_text = f.read()
            
            cleaned_text = clean_text(raw_text)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_text)
            
            print(f'Done: {filename}')

if __name__ == '__main__':
    process_all_texts('book_data/not_clean', 'book_data/cleaned')