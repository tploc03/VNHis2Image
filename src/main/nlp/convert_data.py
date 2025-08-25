import os
import json
import spacy
from spacy.tokens import DocBin
from collections import Counter

SPAN_KEY = "sc"

def convert_doccano_to_spacy(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"Can't find: {input_path}")
        return

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created folder: {output_dir}")

    nlp = spacy.blank("vi")
    db = DocBin()
    total_docs = 0
    total_entities = 0
    skipped_spans = 0
    bad_json_lines = 0
    empty_docs = 0
    label_counter = Counter()

    with open(input_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                bad_json_lines += 1
                print(f"[WARN] Bad JSON at line {line_num}. Skipped.")
                continue

            text = data.get("text", "")
            labels = data.get("label", [])

            if not text.strip():
                print(f"[INFO] Empty text at line {line_num}. Skipped.")
                continue

            doc = nlp.make_doc(text)
            spans = []

            for triplet in labels:
                if not isinstance(triplet, (list, tuple)) or len(triplet) != 3:
                    skipped_spans += 1
                    print(f"[WARN] Bad label format at line {line_num}: {triplet}")
                    continue

                start, end, label = triplet

                while start < end and start < len(text) and text[start].isspace():
                    start += 1
                while end > start and end - 1 < len(text) and text[end - 1].isspace():
                    end -= 1

                start = max(0, min(int(start), len(text)))
                end = max(0, min(int(end), len(text)))
                if start >= end:
                    skipped_spans += 1
                    continue

                span = doc.char_span(start, end, label=label, alignment_mode="contract")
                if span is None:
                    skipped_spans += 1
                    continue

                spans.append(span)

            if spans:
                for s in spans:
                    label_counter[s.label_] += 1
                total_entities += len(spans)
                doc.spans[SPAN_KEY] = spans
            else:
                empty_docs += 1
                doc.spans[SPAN_KEY] = []

            db.add(doc)
            total_docs += 1

    db.to_disk(output_path)
    print(f"Docs total      : {total_docs}")
    print(f"Entities total  : {total_entities}")
    print(f"Empty docs      : {empty_docs}")
    print(f"Skipped spans   : {skipped_spans}")
    print(f"Bad JSON lines  : {bad_json_lines}")
    print(f"Label counts    : {dict(label_counter)}")
    print(f"Done: {input_path} to {output_path}")

if __name__ == "__main__":
    convert_doccano_to_spacy(
        "data/labeled/json_files/v5/train.jsonl",
        "data/labeled/corpus/v5/train.spacy"
    )
    convert_doccano_to_spacy(
        "data/labeled/json_files/v5/dev.jsonl",
        "data/labeled/corpus/v5/dev.spacy"
    )

