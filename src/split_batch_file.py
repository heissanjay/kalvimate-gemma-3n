import os
import json
import logging
import argparse
import tiktoken


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def count_tokens(json_line: str, encoding: tiktoken.Encoding) -> int:
    try:
        obj = json.loads(json_line)
        messages = obj.get("body", {}).get("messages", [])
        if not messages:
            logging.warning("Found a line with no messages to process.")
            return 0
        
        content = "".join(m.get("content", "") for m in messages)
        return len(encoding.encode(content))
        
    except json.JSONDecodeError:
        logging.error(f"Could not decode JSON from line: {json_line.strip()}")
        return 0
    except Exception as e:
        logging.error(f"An unexpected error occurred while counting tokens: {e}")
        return 0


def main(args):
    if not os.path.exists(args.input_file):
        logging.error(f"Input file not found at: {args.input_file}")
        return

    try:
        encoding = tiktoken.encoding_for_model(args.model)
    except KeyError:
        logging.error(f"Model '{args.model}' not found. Please use a valid model name for tiktoken.")
        return

    os.makedirs(args.output_dir, exist_ok=True)
    
    base_name = os.path.splitext(os.path.basename(args.input_file))[0]

    logging.info(f"Starting to process '{args.input_file}' with a token limit of {args.token_limit} per file.")
    
    split_index = 1
    current_token_count = 0
    lines_in_current_file = 0
    
    output_file_path = os.path.join(args.output_dir, f"{base_name}_split_{split_index}.jsonl")
    current_output_file = open(output_file_path, "w", encoding="utf-8")
    logging.info(f"Creating split file: {output_file_path}")

    with open(args.input_file, "r", encoding="utf-8") as f:
        for line in f:
            tokens_in_line = count_tokens(line, encoding)

            if tokens_in_line > args.token_limit:
                logging.warning(f"A single line contains {tokens_in_line} tokens, which exceeds the limit of {args.token_limit}.")

            if lines_in_current_file > 0 and (current_token_count + tokens_in_line > args.token_limit):
                logging.info(f"Token limit reached for split {split_index}. Total tokens: {current_token_count}.")
                current_output_file.close()
                
                split_index += 1
                current_token_count = 0
                lines_in_current_file = 0
                
                output_file_path = os.path.join(args.output_dir, f"{base_name}_split_{split_index}.jsonl")
                current_output_file = open(output_file_path, "w", encoding="utf-8")
                logging.info(f"Creating new split file: {output_file_path}")

            current_output_file.write(line)
            current_token_count += tokens_in_line
            lines_in_current_file += 1
    
    current_output_file.close()
    logging.info(f"Token count for final split {split_index}: {current_token_count}.")
    logging.info(f"Done. Created {split_index} split files in '{args.output_dir}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Splits an OpenAI batch input JSONL file into smaller files based on a token limit."
    )

    parser.add_argument(
        "-i", "--input-file",
        type=str,
        required=True,
        help="Path to the source JSONL input file."
    )

    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default="./openai_inputs",
        help="Directory to save the split files. Defaults to './openai_inputs'."
    )

    parser.add_argument(
        "-l", "--token-limit",
        type=int,
        default=1_500_000,
        help="Maximum number of tokens allowed per split file. Defaults to 1,500,000."
    )
    
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="gpt-4o-mini",
        help="The model used for tokenization (e.g., 'gpt-4o-mini', 'gpt-4'). Defaults to 'gpt-4o-mini'."
    )
    
    args = parser.parse_args()
    main(args)