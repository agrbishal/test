import boto3
from collections import defaultdict
from openpyxl import Workbook

MAX_ITEMS = 20

s3 = boto3.client("s3")


def list_bucket_keys(bucket):
    paginator = s3.get_paginator("list_objects_v2")
    keys = []

    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])

    return keys


def build_tree(keys):
    tree = lambda: defaultdict(tree)
    root = tree()

    for key in keys:
        parts = key.split("/")
        node = root
        for part in parts:
            node = node[part]

    return root


def prune_tree(node):
    """Stop expanding if child count > MAX_ITEMS"""
    if len(node) > MAX_ITEMS:
        return {"EXCEEDED_LIMIT": len(node)}

    new_node = {}
    for k, v in node.items():
        new_node[k] = prune_tree(v)

    return new_node


def write_tree(ws, node, level=0, row=1):
    for key, val in node.items():
        ws.cell(row=row, column=level + 1, value=key)
        row += 1

        if isinstance(val, dict):
            if "EXCEEDED_LIMIT" in val:
                ws.cell(row=row, column=level + 2,
                        value=f"... exceeds {MAX_ITEMS} items")
                row += 1
            else:
                row = write_tree(ws, val, level + 1, row)

    return row


def process_bucket(bucket, wb):
    print(f"Processing {bucket}")

    keys = list_bucket_keys(bucket)
    tree = build_tree(keys)
    pruned = prune_tree(tree)

    ws = wb.create_sheet(title=bucket[:31])
    write_tree(ws, pruned)


def main():
    buckets = [b["Name"] for b in s3.list_buckets()["Buckets"]]

    wb = Workbook()
    wb.remove(wb.active)

    for bucket in buckets:
        process_bucket(bucket, wb)

    wb.save("s3_bucket_structure.xlsx")


if __name__ == "__main__":
    main()
