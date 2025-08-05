import os
import json
import time
import logging
import argparse
from openai import OpenAI
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


load_dotenv()


def main(args):
    try:
        api_key = os.environ.get("API_KEY")
        if not api_key:
            logging.error("API_KEY not found in environment variables. Please check your .env file.")
            return

        client = OpenAI(api_key=api_key)
        
        input_file_path = args.input_file
        if not os.path.exists(input_file_path):
            logging.error(f"Input file not found at: {input_file_path}")
            return
            
        logging.info(f"Found input file: {input_file_path}")

        logging.info("Uploading batch input file to OpenAI...")
        batch_input_file = client.files.create(
            file=open(input_file_path, "rb"), 
            purpose="batch"
        )
        logging.info(f"Successfully uploaded file with ID: {batch_input_file.id}")

        logging.info("Creating new batch job...")
        batch_job = client.batches.create(
            input_file_id=batch_input_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"description": args.description},
        )
        logging.info(f"Successfully created batch job with ID: {batch_job.id}")
        
        initial_response_path = os.path.join(args.output_dir, f"{batch_job.id}_initial_response.json")
        os.makedirs(args.output_dir, exist_ok=True)
        with open(initial_response_path, "w") as f:
            json.dump(batch_job.to_dict(), f, indent=4)
        logging.info(f"Saved initial job details to {initial_response_path}")

        logging.info("Monitoring batch job status. This may take a while...")
        while True:
            retrieved_job = client.batches.retrieve(batch_job.id)
            status = retrieved_job.status
            logging.info(f"Current job status: {status}")

            if status == 'completed':
                logging.info("Batch job completed successfully!")
                break
            elif status in ['failed', 'cancelled']:
                logging.error(f"Batch job {status}. Errors: {retrieved_job.errors}")
                return
            
            time.sleep(60)
            
        output_file_id = retrieved_job.output_file_id
        if not output_file_id:
            logging.error("Job completed but no output file ID was found.")
            return
            
        logging.info(f"Downloading results from output file ID: {output_file_id}")
        file_content_response = client.files.content(output_file_id)
        
        base_input_name = os.path.basename(input_file_path).split('.')[0]
        output_filename = f"result_{base_input_name}_{batch_job.id}.jsonl"
        final_output_path = os.path.join(args.output_dir, output_filename)
        
        with open(final_output_path, "wb") as f:
            f.write(file_content_response.read())
            
        logging.info(f"Successfully downloaded and saved results to: {final_output_path}")

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create and monitor an OpenAI batch job."
    )
    
    parser.add_argument(
        "--input-file",
        type=str,
        required=True,
        help="Path to the JSONL batch input file."
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./clean_outputs",
        help="Directory to save the batch job responses and final results."
    )

    parser.add_argument(
        "--description",
        type=str,
        default="MCQ generation job",
        help="A description for the batch job metadata."
    )
    
    args = parser.parse_args()
    main(args)