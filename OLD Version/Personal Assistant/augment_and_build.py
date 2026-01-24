# augment_and_build.py
# VERSION 2: Now correctly parses markdown [entity](label)

import spacy
from spacy.tokens import DocBin
from data_templates import INTENT_TEMPLATES
import random
import sys
import re

# Regex to find [entity](label)
ENTITY_REGEX = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# --- Simple Augmentation Settings ---
PREFIXES_EN = ["", "please ", "can you ", "will you ", "kindly ", "jarvis, "]
PREFIXES_HI = ["", "कृपया ", "क्या तुम ", "ज़रा ", "जार्विस, "]
NUM_AUGMENTATIONS_PER_EXAMPLE = 5

ALL_INTENTS = list(INTENT_TEMPLATES.keys())


def parse_markdown_example(markdown_text):
    """
    Parses the [entity](label) markdown.
    Returns a clean text and a list of (start, end, label) entities.
    """
    clean_text = ""
    entities = []
    last_end = 0

    for match in ENTITY_REGEX.finditer(markdown_text):
        entity_text = match.group(1)
        entity_label = match.group(2)

        # Add text before this entity
        clean_text += markdown_text[last_end:match.start()]

        # Calculate new start/end
        start = len(clean_text)
        clean_text += entity_text
        end = len(clean_text)

        entities.append((start, end, entity_label))
        last_end = match.end()

    # Add any remaining text
    clean_text += markdown_text[last_end:]

    return clean_text, {"entities": entities}


def create_training_data(templates, num_augmentations):
    try:
        nlp = spacy.blank("xx")
    except ImportError:
        print("\n[Error] Multilingual model 'xx' not found. ")
        print("Please run: python -m spacy download xx_ent_core_web_sm")
        sys.exit()

    db = DocBin()
    print(f"\nAugmenting data for {len(ALL_INTENTS)} intents...")
    total_examples = 0

    for intent, examples in templates.items():
        if not isinstance(examples, list):
            print(f"Warning: Skipping intent '{intent}' because its data is not a list.")
            continue

        for example_tuple in examples:
            if not isinstance(example_tuple, tuple) or len(example_tuple) == 0:
                print(f"Warning: Skipping malformed example in '{intent}': {example_tuple}")
                continue

            # The example_tuple is ("...[text](label)...", {})
            # We ignore the second part ({}) and parse the markdown from the first part.
            markdown_text = example_tuple[0]

            # 1. Parse the original markdown text
            clean_text, annotations = parse_markdown_example(markdown_text)

            # 2. Add the original example
            doc = create_spacy_doc(nlp, clean_text, annotations, intent)
            if doc:
                db.add(doc)
                total_examples += 1

            # 3. Add augmented versions
            is_hindi = any(c >= '\u0900' for c in clean_text)
            prefixes = PREFIXES_HI if is_hindi else PREFIXES_EN

            for _ in range(num_augmentations):
                prefix = random.choice(prefixes)
                if prefix == "":
                    continue

                new_text = prefix + clean_text

                # We must shift all entity offsets by the length of the prefix
                new_annotations = {"entities": []}
                for (start, end, label) in annotations.get("entities", []):
                    new_annotations["entities"].append((start + len(prefix), end + len(prefix), label))

                doc_aug = create_spacy_doc(nlp, new_text, new_annotations, intent)
                if doc_aug:
                    db.add(doc_aug)
                    total_examples += 1

    print(f"Generated {total_examples} total training examples.")
    return db, nlp


def create_spacy_doc(nlp, text, annotations, intent):
    """Creates a spaCy Doc object from clean text and annotations."""
    doc = nlp.make_doc(text)

    # Create category dictionary
    cats = {intent_name: 0.0 for intent_name in ALL_INTENTS}
    cats[intent] = 1.0
    doc.cats = cats

    # Add entities
    ents = []
    for start, end, label in annotations.get("entities", []):
        span = doc.char_span(start, end, label=label)
        if span is None:
            # This warning should be much rarer now
            print(f"Warning: Skipping entity in '{text}' from char {start}-{end} ('{text[start:end]}')")
        else:
            ents.append(span)
    doc.ents = ents

    return doc


if __name__ == "__main__":
    # Check for the multilingual model pack
    try:
        spacy.blank("xx")
    except ImportError:
        print("\n[Error] Multilingual model 'xx' not found. ")
        print("Downloading 'xx_ent_core_web_sm' model pack...")
        try:
            spacy.cli.download("xx_ent_core_web_sm")
            print("Model downloaded. Please run the script again.")
        except Exception as e:
            print(f"Failed to download model: {e}")
            print("Please run manually: python -m spacy download xx_ent_core_web_sm")
        sys.exit()

    all_data, nlp = create_training_data(INTENT_TEMPLATES, NUM_AUGMENTATIONS_PER_EXAMPLE)

    # Split the data (e.g., 80% train, 20% dev)
    docs = list(all_data.get_docs(nlp.vocab))
    random.shuffle(docs)
    split_point = int(len(docs) * 0.8)

    train_docs = docs[:split_point]
    dev_docs = docs[split_point:]

    # Create DocBins for train and dev
    train_db = DocBin(docs=train_docs)
    dev_db = DocBin(docs=dev_docs)

    # Save to disk
    train_db.to_disk("./train.spacy")
    dev_db.to_disk("./dev.spacy")

    print(f"\n✅ Data created: train.spacy ({len(train_docs)} docs), dev.spacy ({len(dev_docs)} docs)")