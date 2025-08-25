import spacy
from spacy import displacy

nlp = spacy.load("models/spancat_v5/model-best")

print("Evaluate Model ")

test_sentences = [
    # "đến nhà tần (246 206 trước công nguyên) lược định phía nam thì đặt làm tượng quận , sau nhà hán (202 trước công nguyên 220 sau công nguyên) dứt nhà triệu , chia đất tượng quận ra làm ba quận là giao chỉ , cửu chân và nhật nam."
    "trận bạch đằng nằm 938."
]

print("\nVisualizing Spans on Test Sentences:")
for text in test_sentences:
    doc = nlp(text)
    print(f"\nText: {text}")
    print("doc.spans:", doc.spans)
    print("doc.ents:", doc.ents)
    if "sc" in doc.spans:
        displacy.render(doc, style="span", jupyter=True, options={"spans_key": "sc"})
    else:
        print("No spans found with key 'sc'")
