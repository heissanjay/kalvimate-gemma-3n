import os
import json
import re
import unicodedata
from typing import Dict, List, Any


class ContentPreprocessor:
    def __init__(self):
        self.math_replacements = {
            r"power minus (\w+)": r"^-\1",
            r"power (\w+)": r"^\1",
            r"metre second power minus two": "m/s²",
            r"kilogram metre second power minus one": "kg⋅m/s",
            r"gram centimeter second power minus two": "g⋅cm/s²",
            r"newton metre": "N⋅m",
            r"dyne centi metre": "dyne⋅cm",
            r"kilogram force": "kgf",
            r"gram force": "gf",
            r"divided by": "/",
            r"times": "×",
            r"minus": "-",
            r"plus": "+",
        }

        self.scientific_patterns = {
            r"10 power(\w+)": r"10^\1",
            r"(\d+) × 10 power (\w+)": r"\1 × 10^\2",
        }

        self.preserve_patterns = [
            r"figure \d+\.\d+",
            r"table \d+\.\d+",
            r"equation \d+\.\d+",
            r"example \d+",
            r"activity \d+\.\d+",
            r"problem \d+",
            r"solution:?",
        ]

    def normalize_unicode(self, text: str) -> str:
        return unicodedata.normalize("NFKC", text)

    def fix_mathematical_notation(self, text: str) -> str:
        result = text
        for pattern, replacement in self.math_replacements.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        for pattern, replacement in self.scientific_patterns.items():
            result = re.sub(pattern, replacement, result)

        return result

    def clean_spacing_and_punctuation(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        text = re.sub(r"([,.;:!?])\s*", r"\1 ", text)
        text = re.sub(r"\s*([=+\-×÷/<>])\s*", r" \1 ", text)
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def preserve_educational_elements(self, text: str) -> str:
        result = text

        for pattern in self.preserve_patterns:
            result = re.sub(
                pattern, lambda m: m.group(0).title(), result, flags=re.IGNORECASE
            )

        return result

    def fix_common_ocr_errors(self, text: str) -> str:
        fixes = {
            r"\bG ravity\b": "Gravity",
            r"\bN ewton\b": "Newton",
            r"\bE arth\b": "Earth",
            r"\bF orce\b": "Force",
            r"\bM ass\b": "Mass",
            r"\bV elocity\b": "Velocity",
            r"\bA cceleration\b": "Acceleration",
            r"\bM omentum\b": "Momentum",
            r"\bI nertia\b": "Inertia",
            r"\betcetera\b": "etc.",
            r"\bdash\b": "—",
            r"\bbracket\s+([^)]+)\s+bracket": r"(\1)",
        }

        result = text
        for pattern, replacement in fixes.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result

    def smart_sentence_splitting(self, text: str) -> List[str]:
        sentences = []
        current = ""

        i = 0
        while i < len(text):
            char = text[i]
            current += char
            if char == ".":
                if i + 1 < len(text):
                    next_char = text[i + 1]
                    if next_char == " " and i + 2 < len(text) and text[i + 2].isupper():
                        sentences.append(current.strip())
                        current = ""
                    elif next_char.isdigit():
                        pass
                else:
                    sentences.append(current.strip())
                    current = ""

            i += 1

        if current.strip():
            sentences.append(current.strip())

        return [s for s in sentences if s]

    def preprocess_text(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        text = self.normalize_unicode(text)
        text = self.fix_mathematical_notation(text)
        text = self.fix_common_ocr_errors(text)
        text = self.clean_spacing_and_punctuation(text)
        text = self.preserve_educational_elements(text)
        text = text.strip()

        return text

    def preprocess_content_list(self, content_list: List[str]) -> List[str]:
        processed = []

        for item in content_list:
            cleaned = self.preprocess_text(item)
            if cleaned:
                processed.append(cleaned)

        return processed

    def preprocess_chapter_structure(
        self, chapter_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        processed_data = chapter_data.copy()

        if "chapter_title" in processed_data:
            processed_data["chapter_title"] = self.preprocess_text(
                processed_data["chapter_title"]
            )

        if "TOPIC WISE SECTIONS" in processed_data:
            for topic in processed_data["TOPIC WISE SECTIONS"]:
                if "topic_title" in topic:
                    topic["topic_title"] = self.preprocess_text(topic["topic_title"])
                if "content" in topic:
                    topic["content"] = self.preprocess_content_list(topic["content"])
                if "sub_topics" in topic:
                    for sub_topic in topic["sub_topics"]:
                        if "topic_title" in sub_topic:
                            sub_topic["topic_title"] = self.preprocess_text(
                                sub_topic["topic_title"]
                            )
                        if "content" in sub_topic:
                            sub_topic["content"] = self.preprocess_content_list(
                                sub_topic["content"]
                            )
        if "SOLVED PROBLEMS" in processed_data:
            for problem in processed_data["SOLVED PROBLEMS"]:
                if "topic_title" in problem:
                    problem["topic_title"] = self.preprocess_text(
                        problem["topic_title"]
                    )
                if "content" in problem:
                    problem["content"] = self.preprocess_content_list(
                        problem["content"]
                    )

        return processed_data


def preprocess_chapter_file(
    input_path: str, output_path: str, preprocessor: ContentPreprocessor
):
    try:
        print(f"Processing {input_path}...")
        with open(input_path, "r", encoding="utf-8") as f:
            chapter_data = json.load(f)
        processed_data = preprocessor.preprocess_chapter_structure(chapter_data)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=4)
        print(f"✓ Successfully preprocessed and saved to {output_path}")
        original_content_items = sum(
            len(topic.get("content", []))
            for topic in chapter_data.get("TOPIC WISE SECTIONS", [])
        )
        processed_content_items = sum(
            len(topic.get("content", []))
            for topic in processed_data.get("TOPIC WISE SECTIONS", [])
        )

        print(f"  Content items: {original_content_items} → {processed_content_items}")

        return True

    except Exception as e:
        print(f"✗ Error processing {input_path}: {e}")
        return False


if __name__ == "__main__":
    input_directory = "structured_chapters"
    output_directory = "preprocessed_chapters"
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
        print(f"Created output directory: {output_directory}")
    preprocessor = ContentPreprocessor()
    json_files = [f for f in os.listdir(input_directory) if f.endswith(".json")]

    if not json_files:
        print(f"No JSON files found in {input_directory}")
        raise

    print(f"Found {len(json_files)} JSON files to process")
    print("-" * 50)

    successful = 0
    total = len(json_files)

    for filename in json_files:
        input_file_path = os.path.join(input_directory, filename)
        output_file_path = os.path.join(output_directory, filename)

        if preprocess_chapter_file(input_file_path, output_file_path, preprocessor):
            successful += 1

        print()

    print("-" * 50)
    print(f"Processing complete: {successful}/{total} files processed successfully")
