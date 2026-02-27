import json
import subprocess
from datetime import datetime
from openpyxl import Workbook

# -------------------------------
# Helpers
# -------------------------------

def get_account_id():
    try:
        out = subprocess.check_output(
            ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"]
        )
        return out.decode().strip()
    except:
        return "UNKNOWN"

def extract_tags(tag_list):
    return {t["Key"]: t["Value"] for t in tag_list} if tag_list else {}

# -------------------------------
# Workbook setup
# -------------------------------

wb = Workbook()
wb.remove(wb.active)

def add_sheet(name, headers):
    ws = wb.create_sheet(name)
    ws.append(headers)
    return ws

# -------------------------------
# README
# -------------------------------

readme_ws = add_sheet("README", ["Item", "Value"])

readme_ws.append(["Workbook Purpose", "AWS resource inventory and workflow documentation"])
readme_ws.append(["AWS Account ID", get_account_id()])
readme_ws.append(["Environments", "dev and prod in same account"])
readme_ws.append(["Generated On", datetime.utcnow().isoformat()])
readme_ws.append(["Data Source", "AWS CLI (read-only)"])
readme_ws.append(["Not Auto-Collected", "Airflow DAGs, Snowflake, business logic"])
readme_ws.append(["Next Steps", "Fix tags, complete DEV and PROD workflows"])

# -------------------------------
# MASTER INVENTORY
# -------------------------------

inventory_ws = add_sheet("01_Resource_Inventory", [
    "Environment",
    "Service",
    "Resource Type",
    "Resource Name",
    "Resource ID",
    "Region",
    "Purpose",
    "Application",
    "Owner",
    "Depends On",
    "Used By",
    "Notes"
])

# -------------------------------
# EC2
# -------------------------------

ec2_ws = add_sheet("03_EC2", [
    "Environment",
    "Name",
    "InstanceId",
    "InstanceType",
    "State",
    "VPC",
    "Subnet",
    "IAM Role",
    "Hosted Services"
])

with open("collect/ec2.json") as f:
    ec2_data = json.load(f)

for r in ec2_data["Reservations"]:
    for i in r["Instances"]:
        tags = extract_tags(i.get("Tags"))
        env = tags.get("Environment")
        name = tags.get("Name")

        ec2_ws.append([
            env,
            name,
            i["InstanceId"],
            i["InstanceType"],
            i["State"]["Name"],
            i.get("VpcId"),
            i.get("SubnetId"),
            i.get("IamInstanceProfile", {}).get("Arn"),
            ""
        ])

        inventory_ws.append([
            env,
            "EC2",
            "Instance",
            name,
            i["InstanceId"],
            "",
            "",
            tags.get("Application"),
            tags.get("Owner"),
            "",
            "",
            "Hosts Airflow / APIs / batch jobs"
        ])

# -------------------------------
# LAMBDA
# -------------------------------

lambda_ws = add_sheet("05_Lambda", [
    "Environment",
    "Function Name",
    "Runtime",
    "Timeout",
    "Role",
    "Trigger",
    "Source",
    "Destination"
])

with open("collect/lambda.json") as f:
    lambda_data = json.load(f)

for fn in lambda_data["Functions"]:
    lambda_ws.append([
        "",
        fn["FunctionName"],
        fn["Runtime"],
        fn["Timeout"],
        fn["Role"],
        "",
        "",
        ""
    ])

    inventory_ws.append([
        "",
        "Lambda",
        "Function",
        fn["FunctionName"],
        fn["FunctionArn"],
        "",
        "",
        "",
        "",
        "",
        "",
        ""
    ])

# -------------------------------
# S3
# -------------------------------

s3_ws = add_sheet("06_S3", [
    "Environment",
    "Bucket Name",
    "Purpose",
    "Data Type",
    "Encryption",
    "Lifecycle",
    "Triggered Services"
])

with open("collect/s3.json") as f:
    s3_data = json.load(f)

for b in s3_data["Buckets"]:
    s3_ws.append([
        "",
        b["Name"],
        "",
        "",
        "",
        "",
        ""
    ])

    inventory_ws.append([
        "",
        "S3",
        "Bucket",
        b["Name"],
        b["Name"],
        "",
        "",
        "",
        "",
        "",
        "",
        ""
    ])

# -------------------------------
# SQS
# -------------------------------

sqs_ws = add_sheet("07_SQS", [
    "Environment",
    "Queue Name",
    "Type",
    "Producer",
    "Consumer",
    "DLQ",
    "Purpose"
])

with open("collect/sqs.json") as f:
    sqs_data = json.load(f)

for q in sqs_data.get("QueueUrls", []):
    name = q.split("/")[-1]

    sqs_ws.append([
        "",
        name,
        "",
        "",
        "",
        "",
        ""
    ])

    inventory_ws.append([
        "",
        "SQS",
        "Queue",
        name,
        q,
        "",
        "",
        "",
        "",
        "",
        "",
        ""
    ])

# -------------------------------
# WORKFLOWS
# -------------------------------

add_sheet("10_DEV_Workflow", [
    "Step",
    "Service",
    "Resource",
    "Action",
    "Output",
    "Next Step"
])

add_sheet("11_PROD_Workflow", [
    "Step",
    "Service",
    "Resource",
    "Action",
    "Output",
    "Next Step"
])

# -------------------------------
# SAVE
# -------------------------------

wb.save("resources_inventory.xlsx")
print("✅ resources_inventory.xlsx generated successfully")
