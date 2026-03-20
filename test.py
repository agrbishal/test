
------config.py------
import os

ENV = os.getenv("ENV", "dev")

CONFIG = {
    "dev": {
        "bucket": "my-dev-bucket",
        "source_prefix": "incoming/",
        "target_prefix_move": "processed/",
        "target_prefix_processed": "split/",
        "file_move_pattern": "inventory",
        "file_process_pattern": "sales",
        "split_column": "Region",
        "modify_column": "Category"
    },
    "prod": {
        "bucket": "my-prod-bucket",
        "source_prefix": "incoming/",
        "target_prefix_move": "processed/",
        "target_prefix_processed": "split/",
        "file_move_pattern": "inventory",
        "file_process_pattern": "sales",
        "split_column": "Region",
        "modify_column": "Category"
    }
}

def get_config():
    return CONFIG[ENV]
---------------------processor.py-----------

import pandas as pd
import os
import boto3

s3 = boto3.client("s3")


def process_excel(bucket, key, config):

    local_input = "/tmp/input.xlsx"
    s3.download_file(bucket, key, local_input)

    df = pd.read_excel(local_input)

    split_col = config["split_column"]
    modify_col = config["modify_column"]

    unique_values = df[split_col].dropna().unique()

    output_files = []

    for val in unique_values:
        sub_df = df[df[split_col] == val].copy()

        # Modify column
        sub_df[modify_col] = f"{val}_processed"

        output_file = f"/tmp/output_{val}.xlsx"
        sub_df.to_excel(output_file, index=False)

        output_files.append((val, output_file))

    return output_files


def upload_processed_files(bucket, original_key, files, config):

    base_name = os.path.basename(original_key)

    for val, file_path in files:

        new_key = f"{config['target_prefix_processed']}{val}_{base_name}"

        s3.upload_file(file_path, bucket, new_key)

        print(f"Uploaded: {new_key}")




------------------------------------lambda_function.py--------
import json
import boto3
import os
from urllib.parse import unquote_plus
from config import get_config
from processor import process_excel, upload_processed_files

s3 = boto3.client("s3")


def move_file(bucket, key, config):

    new_key = config["target_prefix_move"] + os.path.basename(key)

    s3.copy_object(
        Bucket=bucket,
        CopySource={'Bucket': bucket, 'Key': key},
        Key=new_key
    )

    s3.delete_object(Bucket=bucket, Key=key)

    print(f"Moved file: {key} → {new_key}")


def lambda_handler(event, context):

    config = get_config()

    for record in event['Records']:

        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])

        filename = os.path.basename(key)

        print(f"Processing: {filename}")

        # Case 1: MOVE only
        if config["file_move_pattern"] in filename:
            move_file(bucket, key, config)

        # Case 2: PROCESS + SPLIT
        elif config["file_process_pattern"] in filename:

            processed_files = process_excel(bucket, key, config)

            upload_processed_files(bucket, key, processed_files, config)

            # optionally delete original
            s3.delete_object(Bucket=bucket, Key=key)

        else:
            print("File doesn't match any rule")

    return {
        "statusCode": 200,
        "body": json.dumps("Done")
    }
