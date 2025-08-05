import os
import json
import logging
import argparse
from typing import List, Dict, Any

from datasets import Dataset
from dotenv import load_dotenv
from huggingface_hub import HfApi, HfFolder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

SYSTEM_MESSAGE = {
    "role": "system",
    "content": "You are KalviMate, a friendly, patient, and encouraging AI tutor. Your purpose is to help students from rural government schools in India learn from their state board syllabus. Explain concepts simply, use relatable examples, and always be supportive. Your knowledge is based strictly on the provided textbook content."
}

def load_and_parse_batch_outputs(directory: str) -> List[Dict[str, Any]]:
    if not os.path.isdir(directory):
        logging.error(f"Input directory not found: {directory}")
        return []

    output_files = sorted([f for f in os.listdir(directory) if f.endswith(".jsonl")])
    logging.info(f"Found {len(output_files)} files to process in '{directory}'.")
    
    all_responses = []
    for filename in output_files:
        filepath = os.path.join(directory, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                try:
                    result_obj = json.loads(line)
                except json.JSONDecodeError:
                    logging.warning(f"[{filename}:{i}] Skipping line due to JSON decode error.")
                    continue

                if result_obj.get("error"):
                    logging.warning(f"[{filename}:{i}] Skipping line due to OpenAI API error.")
                    continue

                content_str = result_obj.get("response", {}).get("body", {}).get('choices', [{}])[0].get("message", {}).get("content")
                if not content_str:
                    logging.warning(f"[{filename}:{i}] Skipping line due to missing content.")
                    continue
                
                try:
                    model_response = json.loads(content_str)
                    all_responses.append(model_response)
                except json.JSONDecodeError:
                    logging.warning(f"[{filename}:{i}] Skipping line due to content JSON decode error.")
    
    logging.info(f"Successfully parsed {len(all_responses)} model responses.")
    return all_responses

def normalize_and_clean(responses: List[Any]) -> List[List[Dict[str, str]]]:
    unwrapped = [list(res.values())[0] if isinstance(res, dict) and len(res) == 1 else res for res in responses]

    flattened = []
    for conv in unwrapped:
        flat_conv = []
        if isinstance(conv, list):
            for item in conv:
                if isinstance(item, list):
                    flat_conv.extend(item)
                else:
                    flat_conv.append(item)
            flattened.append(flat_conv)
        else:
            logging.warning(f"Skipping item that is not a list: {type(conv)}")

    cleaned_conversations = []
    for conv in flattened:
        if not conv:
            continue
        
        valid_conv = []
        for msg in conv:
            if not isinstance(msg, dict): continue
            
            if 'assistant' in msg and not msg.get('content'):
                msg['content'] = msg.pop('assistant')
            
            msg = {k: v for k, v in msg.items() if k in ['role', 'content']}
            
            if 'role' in msg and 'content' in msg:
                valid_conv.append(msg)

        if not valid_conv: continue
        no_repeats_conv = [valid_conv[0]]
        for msg in valid_conv[1:]:
            if msg['role'] != no_repeats_conv[-1]['role']:
                no_repeats_conv.append(msg)
        
        cleaned_conversations.append(no_repeats_conv)
        
    logging.info(f"Normalized and cleaned conversations. Count: {len(cleaned_conversations)}")
    return cleaned_conversations

def add_system_message_and_validate(conversations: List[List[Dict[str, str]]], system_message: Dict[str, str]) -> List[List[Dict[str, str]]]:
    final_conversations = []
    for conv in conversations:
        if conv and conv[0]['role'] == 'user':
            final_conversations.append([system_message.copy()] + conv)
    
    for i, conv in enumerate(final_conversations):
        roles = [msg['role'] for msg in conv]
        if roles[1] != 'user':
            logging.warning(f"Conversation {i} does not start with 'user' after system message.")
        for j in range(1, len(roles) - 1):
            if roles[j] == roles[j+1]:
                logging.warning(f"Found consecutive identical roles in final conversation {i}.")

    logging.info(f"Added system message to {len(final_conversations)} conversations.")
    return final_conversations

def create_and_push_to_hub(conversations: List[List[Dict[str, str]]], repo_id: str, token: str):
    if not conversations:
        logging.error("No valid conversations to upload. Aborting.")
        return

    logging.info(f"Preparing dataset with {len(conversations)} conversations for Hugging Face Hub.")
    
    hf_dataset_data = [{"messages": conv} for conv in conversations]
    
    hf_dataset = Dataset.from_list(hf_dataset_data)

    logging.info(f"Pushing dataset to '{repo_id}'...")
    hf_dataset.push_to_hub(repo_id=repo_id, token=token, private=False)
    logging.info("Successfully pushed dataset to the Hub!")

def main(args):
    load_dotenv()
    hf_token = os.environ.get("HF_TOKEN")
    
    if not args.no_upload and not hf_token:
        logging.error("Hugging Face token not found. Please set HF_TOKEN in your .env file or use --no-upload.")
        return

    raw_responses = load_and_parse_batch_outputs(args.input_dir)
    
    cleaned_conversations = normalize_and_clean(raw_responses)
    
    final_conversations = add_system_message_and_validate(cleaned_conversations, SYSTEM_MESSAGE)
    
    if args.no_upload:
        output_file = "processed_dataset.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_conversations, f, indent=2, ensure_ascii=False)
        logging.info(f"Dry run complete. Processed data saved to '{output_file}'.")
    else:
        create_and_push_to_hub(final_conversations, args.repo_id, hf_token)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Clean, process, and upload OpenAI batch job outputs to the Hugging Face Hub."
    )
    
    parser.add_argument(
        "--input-dir",
        type=str,
        default="./clean_outputs",
        help="Directory containing the raw .jsonl output files from OpenAI."
    )
    
    parser.add_argument(
        "--repo-id",
        type=str,
        default="heissanjay/km-fullset-all-final-sm-full-conv",
        help="The Hugging Face Hub repository ID to push the dataset to."
    )
    
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Run the entire cleaning process but do not upload to the Hub. Saves the result to a local file instead."
    )
    
    args = parser.parse_args()
    main(args)
