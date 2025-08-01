import os
import json
import re


class FileHandler:
    def read_json(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading JSON file {path}: {e}")
            return None

    def read_txt(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError as e:
            print(f"Error reading text file {path}: {e}")
            return None


class PromptGenerator:
    def __init__(
        self,
        chapters_dir="preprocessed_chapters",
        prompts_dir="prompts",
        output_base_dir="chapter_inputs",
    ):
        self.chapters_dir = chapters_dir
        self.prompts_dir = prompts_dir
        self.output_base_dir = output_base_dir
        self.file_handler = FileHandler()
        self.total_files_generated = 0
        self.total_topics_processed = 0
        self.total_input_chars = 0

    def _clean_and_prepare_topic_text(self, topic_data):
        if not topic_data or not isinstance(topic_data, dict):
            return None
        topic_title = topic_data.get("topic_title", "N/A").strip()
        content_list = topic_data.get("content", [])
        cleaned_content = [
            line.strip() for line in content_list if line and len(line.strip()) > 15
        ]
        if not cleaned_content:
            return None
        topic_content_str = "\n".join(cleaned_content)
        return f"Topic Title: {topic_title}\n\nContent:\n{topic_content_str}"

    def generate(self):
        os.makedirs(self.output_base_dir, exist_ok=True)

        if not os.path.isdir(self.chapters_dir) or not os.path.isdir(self.prompts_dir):
            print(
                f"Error: Ensure '{self.chapters_dir}' and '{self.prompts_dir}' directories exist."
            )
            return

        chapter_files = sorted(
            [f for f in os.listdir(self.chapters_dir) if f.endswith(".json")]
        )
        prompt_files = sorted(
            [f for f in os.listdir(self.prompts_dir) if f.endswith(".txt")]
        )

        if not chapter_files or not prompt_files:
            print("Error: No chapter or prompt files found.")
            return

        prompt_templates = {
            os.path.splitext(pf)[0]: self.file_handler.read_txt(
                os.path.join(self.prompts_dir, pf)
            )
            for pf in prompt_files
        }

        for chapter_file in chapter_files:
            chapter_path = os.path.join(self.chapters_dir, chapter_file)
            chapter_data = self.file_handler.read_json(chapter_path)

            if not chapter_data or "TOPIC WISE SECTIONS" not in chapter_data:
                continue

            chapter_number = chapter_data.get("chapter_number", "unknown")
            chapter_dir = os.path.join(
                self.output_base_dir, f"chapter_{chapter_number}"
            )
            os.makedirs(chapter_dir, exist_ok=True)
            topics_to_process = chapter_data.get("TOPIC WISE SECTIONS", [])
            for topic in topics_to_process:
                clean_topic_text = self._clean_and_prepare_topic_text(topic)
                if not clean_topic_text:
                    continue

                self.total_topics_processed += 1
                topic_num_raw = topic.get(
                    "topic_number", str(self.total_topics_processed)
                )
                topic_dir_name = f"topic_{re.sub(r'[^0-9a-zA-Z_]', '_', topic_num_raw)}"
                topic_dir = os.path.join(chapter_dir, topic_dir_name)
                os.makedirs(topic_dir, exist_ok=True)

                for prompt_name, prompt_template in prompt_templates.items():
                    if not prompt_template:
                        continue

                    user_content = prompt_template.replace(
                        "{{topic_text}}", clean_topic_text
                    )
                    self.total_input_chars += len(user_content)

                    api_payload = {
                        "messages": [{"role": "user", "content": user_content}]
                    }
                    output_filepath = os.path.join(topic_dir, f"{prompt_name}.json")

                    with open(output_filepath, "w", encoding="utf-8") as f:
                        json.dump(api_payload, f, indent=4, ensure_ascii=False)

                    self.total_files_generated += 1

        print(
            f"\nSuccessfully generated {self.total_files_generated} input files from {self.total_topics_processed} valid topics across {len(chapter_files)} chapters."
        )
        print(f"Output files are saved in the '{self.output_base_dir}' directory.")


if __name__ == "__main__":
    generator = PromptGenerator()
    generator.generate()
