import os
import json
import re

class BatchInputGenerator:
    def __init__(
        self,
        chapters_dir="preprocessed_chapters",
        prompts_dir="prompts",
        output_file="openai_batch_input_file.jsonl",
    ):
        self.chapters_dir = chapters_dir
        self.prompts_dir = prompts_dir
        self.output_file = output_file
        self.total_requests = 0
        self.total_topics_processed = 0
        self.total_input_chars = 0

    def read_json_file(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading JSON file {file_path}: {e}")
            return None

    def read_txt_file(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError as e:
            print(f"Error reading text file {file_path}: {e}")
            return None

    def estimate_openai_cost(self, num_prompts, total_input_tokens, num_topics, prices):
        # Using a more dynamic calculation based on prompt averages
        prompt_avg_tokens = {
            'MCQ_based': 1500, 'detailed_topic_breakdown': 4000, 
            'rapid_intuition_based_qna': 2000, 'real_world_or_casual_style': 3000, 
            'smart_assistant': 200
        }
        # Total output is the sum of averages for each prompt type, multiplied by the number of topics
        total_output_tokens = num_topics * 1000
        
        batch_discount = 0.5
        input_cost = (total_input_tokens / 1_000_000) * prices["input"] * batch_discount
        output_cost = (total_output_tokens / 1_000_000) * prices["output"] * batch_discount
        total_cost = input_cost + output_cost
        
        print("\n--- OpenAI Batch API Cost Estimation ---")
        print(f"Model: gpt-4o-mini")
        print(f"Price per 1M input tokens: ${prices['input']:.2f} (Standard)")
        print(f"Price per 1M output tokens: ${prices['output']:.2f} (Standard)")
        print("NOTE: A 50% discount is applied for Batch API usage.")
        print("-" * 35)
        print(f"Total API requests in batch file: {num_prompts}")
        print(f"Total unique topics processed: {int(num_topics)}")
        print(f"Estimated total input tokens: {int(total_input_tokens):,}")
        print(f"Estimated total output tokens: {int(total_output_tokens):,}")
        print("-" * 35)
        print(f"Estimated Input Cost (with 50% discount): ${input_cost:.2f}")
        print(f"Estimated Output Cost (with 50% discount): ${output_cost:.2f}")
        print(f"Estimated Total Cost for Batch Job: ${total_cost:.2f}")

    def generate(self):
        if not os.path.isdir(self.chapters_dir) or not os.path.isdir(self.prompts_dir):
            print(f"Error: Ensure '{self.chapters_dir}' and '{self.prompts_dir}' directories exist.")
            return

        chapter_files = sorted([f for f in os.listdir(self.chapters_dir) if f.endswith(".json")])
        prompt_files = sorted([f for f in os.listdir(self.prompts_dir) if f.endswith(".txt")])

        if not chapter_files or not prompt_files:
            print("Error: No chapter or prompt files found.")
            return

        prompt_templates = {os.path.splitext(pf)[0]: self.read_txt_file(os.path.join(self.prompts_dir, pf)) for pf in prompt_files}

        with open(self.output_file, "w", encoding="utf-8") as f_out:
            for chapter_file in chapter_files:
                chapter_path = os.path.join(self.chapters_dir, chapter_file)
                chapter_data = self.read_json_file(chapter_path)
                
                if not chapter_data or "TOPIC WISE SECTIONS" not in chapter_data:
                    continue
                
                chapter_number = chapter_data.get("chapter_number", "unknown")
                
                for topic in chapter_data.get("TOPIC WISE SECTIONS", []):
                    self.total_topics_processed += 1
                    topic_num_raw = topic.get("topic_number", str(self.total_topics_processed))
                    topic_title = topic.get("topic_title", "N/A")
                    topic_content = "\n".join(topic.get("content", []))
                    topic_text = f"Topic Title: {topic_title}\n\nContent:\n{topic_content}"

                    for prompt_name, prompt_template in prompt_templates.items():
                        if not prompt_template:
                            continue
                        
                        user_content = prompt_template.replace("{{topic_text}}", topic_text)
                        self.total_input_chars += len(user_content)
                        
                        custom_id = f"req_{self.total_requests}_chap{chapter_number}_topic{topic_num_raw.replace('.', '_')}_{prompt_name}"
                        
                        request_body = {
                            "model": "gpt-4o-mini",
                            "messages": [{"role": "user", "content": user_content}],
                            "response_format": {"type": "json_object"},
                        }
                        
                        batch_request = {
                            "custom_id": custom_id,
                            "method": "POST",
                            "url": "/v1/chat/completions",
                            "body": request_body,
                        }
                        
                        f_out.write(json.dumps(batch_request) + "\n")
                        self.total_requests += 1 

        print(f"\nSuccessfully generated {self.total_requests} API requests into the file '{self.output_file}'.")
        print("This file is now ready for the OpenAI Batch API.")
        
        estimated_input_tokens = self.total_input_chars / 4.0
        gpt4o_mini_prices = {"input": 0.15, "output": 0.60}
        num_topics = self.total_topics_processed
        
        self.estimate_openai_cost(self.total_requests, estimated_input_tokens, num_topics, gpt4o_mini_prices)

if __name__ == "__main__":
    generator = BatchInputGenerator()
    generator.generate()