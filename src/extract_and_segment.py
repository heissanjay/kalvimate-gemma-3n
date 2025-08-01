import os
import re
import json
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


class EPUBTextExtractor:
    def __init__(self, epub_path, output_dir="structured_chapters"):
        self.epub_path = epub_path
        self.output_dir = output_dir
        self.chapter_count = 0
        self.current_chapter_data = None
        self.current_topic = None
        self.in_skipped_section = False
        self.awaiting_chapter_title_completion = False
        self.book = None
        self.toc_files = []

    def clean_text(self, text):
        return re.sub(r"\s+", " ", text).strip()

    def is_new_chapter_heading(self, text, tag_name):
        return tag_name in ["h1", "h2"] and re.match(r"^unit\s*-*\s*\d+", text.lower())

    def is_topic_heading(self, text, tag_name):
        if not tag_name.startswith("h"):
            return False
        if re.match(r"^\d+(\.\d+)*", text):
            return True
        patterns = [
            r"^(introduction|definition|properties|characteristics|types|examples)",
            r"^(method|procedure|process|technique|approach)",
            r"^(application|uses|importance|significance)",
            r"solved\s+problem",
            r"example\s*\d*",
        ]
        return any(re.search(p, text.lower()) for p in patterns)

    def should_skip_section(self, text):
        keywords = [
            "table of contents",
            "learning objectives",
            "reference books",
            "glossary",
            "textbook evaluation",
            "points to remember",
            "ict corner",
            "practicals",
            "concept map",
            "index",
            "bibliography",
        ]
        return any(k in text.lower() for k in keywords)

    def should_skip_line(self, text):
        patterns = [
            r"^figure\s*\d*:",
            r"^table\s*\d*:",
            r"^fig\s*\d*\.",
            r"^\s*\d+\s*$",
            r"^\s*[a-z]\)\s*$",
            r"^\s*\([a-z]\)\s*$",
        ]
        return any(re.match(p, text.lower()) for p in patterns)

    def save_chapter(self):
        chapter_data = self.current_chapter_data
        if not chapter_data:
            return

        for section in ["TOPIC WISE SECTIONS", "SOLVED PROBLEMS"]:
            if section in chapter_data:
                chapter_data[section] = [
                    t
                    for t in chapter_data[section]
                    if t.get("content") or t.get("sub_topics")
                ]
                if not chapter_data[section]:
                    del chapter_data[section]

        if not chapter_data.get("TOPIC WISE SECTIONS") and not chapter_data.get(
            "SOLVED PROBLEMS"
        ):
            print(
                f"Skipping empty chapter: {chapter_data.get('chapter_title', 'Unknown Title')}"
            )
            return

        filename = f"chapter_{chapter_data['chapter_number']}.json"
        path = os.path.join(self.output_dir, filename)

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(chapter_data, f, ensure_ascii=False, indent=4)
            print(f"Successfully saved: {path}")
            print(
                f"  - Topics: {len(chapter_data.get('TOPIC WISE SECTIONS', []))}, "
                f"Problems: {len(chapter_data.get('SOLVED PROBLEMS', []))}"
            )
        except IOError as e:
            print(f"Error writing file {path}: {e}")

    def extract(self):
        try:
            self.book = epub.read_epub(self.epub_path)
            os.makedirs(self.output_dir, exist_ok=True)
            print(f"Created output directory: {self.output_dir}")
        except Exception as e:
            print(f"Fatal Error: Could not read EPUB file. Details: {e}")
            return

        self.toc_files = [
            item.get_name()
            for item in self.book.get_items_of_type(ebooklib.ITEM_NAVIGATION)
        ]
        print(f"Identified ToC files to skip: {self.toc_files}")

        for item in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            if item.get_name() in self.toc_files:
                continue
            self.process_document(item)

        if self.current_chapter_data:
            self.save_chapter()
        print(f"\nExtraction complete. Processed {self.chapter_count} chapters.")

    def process_document(self, item):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        body = soup.find("body")
        if not body:
            return

        for elem in body.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "li"]
        ):
            text = elem.get_text(strip=True)
            if not text or self.should_skip_line(text):
                continue

            tag = elem.name
            is_heading = tag.startswith("h")
            print(f"Processing: [{tag}] {text[:100]}...")

            if is_heading and self.is_new_chapter_heading(text, tag):
                if self.current_chapter_data:
                    self.save_chapter()
                self.start_new_chapter(text)
                continue

            if (
                self.awaiting_chapter_title_completion
                and is_heading
                and not self.should_skip_section(text)
            ):
                self.complete_chapter_title(text)
                continue

            if not self.current_chapter_data:
                continue

            if is_heading and self.should_skip_section(text):
                self.in_skipped_section = True
                self.current_topic = None
                print(f"Entering skipped section: {text}")
                continue

            if is_heading and self.is_topic_heading(text, tag):
                self.add_new_topic(text)
                continue

            if not is_heading and not self.in_skipped_section and self.current_topic:
                self.add_content_to_topic(text)

    def start_new_chapter(self, heading_text):
        self.chapter_count += 1
        self.current_chapter_data = {
            "chapter_number": self.chapter_count,
            "chapter_title": self.clean_text(heading_text),
            "TOPIC WISE SECTIONS": [],
            "SOLVED PROBLEMS": [],
        }
        self.current_topic = None
        self.in_skipped_section = False
        self.awaiting_chapter_title_completion = True
        print(
            f"Started new chapter {self.chapter_count}: {self.current_chapter_data['chapter_title']}"
        )

    def complete_chapter_title(self, text):
        self.current_chapter_data["chapter_title"] += f" - {self.clean_text(text)}"
        self.awaiting_chapter_title_completion = False
        print(f"Completed chapter title: {self.current_chapter_data['chapter_title']}")

    def add_new_topic(self, heading_text):
        self.in_skipped_section = False
        self.awaiting_chapter_title_completion = False

        section_key = (
            "SOLVED PROBLEMS"
            if "solved" in heading_text.lower() and "problem" in heading_text.lower()
            else "TOPIC WISE SECTIONS"
        )
        topic_title = self.clean_text(heading_text)

        topic = {"topic_title": topic_title, "content": []}
        match = re.match(r"^(\d+(?:\.\d+)*)", topic_title)
        if match:
            topic["topic_number"] = match.group(1)

        self.current_chapter_data[section_key].append(topic)
        self.current_topic = topic
        print(f"Created new topic: {topic_title}")

    def add_content_to_topic(self, raw_text):
        text = self.clean_text(raw_text)
        if text and len(text) > 10:
            self.current_topic["content"].append(text)
            print(f"Added content: {text[:50]}...")


if __name__ == "__main__":
    epub_file_path = "/datasource/textbook.epub"
    output_directory = "structured_chapters"
    extractor = EPUBTextExtractor(epub_file_path, output_directory)
    extractor.extract()
