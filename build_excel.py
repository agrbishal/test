import json
import pandas as pd
from openpyxl import Workbook

wb = Workbook()
wb.remove(wb.active)

def add_sheet(name, columns):
    ws = wb.create_sheet(name)
    ws.append(columns)
    return ws

# ---------- SHEETS ----------
add_sheet("README", [
    "Purpose", "Account ID", "Regions", "Owner", "Last Updated", "Notes"
])

add_sheet("01_Resource_Inventory", [
    "Environment", "Service", "Resource Type", "Resource Name",
    "Resource ID", "Region", "Purpose", "Application",
    "Owner", "Depends On", "Used By", "Notes"
])

ec2_ws = add_sheet("03_EC2", [
    "Environment", "Name", "InstanceId", "InstanceType",
    "State", "VPC", "Subnet", "IAM Role", "Hosted Services"
])

lambda_ws = add_sheet("05_Lambda", [
    "Environment", "FunctionName", "Runtime",
    "Timeout", "Role", "Trigger", "Source", "Destination"
])

s3_ws = add_sheet("06_S3", [
    "Environment", "BucketName", "Purpose",
    "Data Type", "Encryption", "Lifecycle", "Triggered Services"
])

sqs_ws = add_sheet("07_SQS", [
    "Environment", "QueueName", "Type",
    "Producer", "Consumer", "DLQ", "Purpose"
])

cw_ws = add_sheet("09_Monitoring", [
    "Environment", "AlarmName", "Metric",
    "Threshold", "Resource", "Action"
])

add_sheet("10_DEV_Workflow", [
    "Step", "Service", "Resource",
    "Action", "Output", "Next Step"
])

add_sheet("11_PROD_Workflow", [
    "Step", "Service", "Resource",
    "Action", "Output", "Next Step"
])

# ---------- POPULATE EC2 ----------
with open("collect/ec2.json") as f:
    data = json.load(f)

for r in data["Reservations"]:
    for i in r["Instances"]:
        tags = {t["Key"]: t["Value"] for t in i.get("Tags", [])}
        ec2_ws.append([
            tags.get("Environment"),
            tags.get("Name"),
            i["InstanceId"],
            i["InstanceType"],
            i["State"]["Name"],
            i.get("VpcId"),
            i.get("SubnetId"),
            i.get("IamInstanceProfile", {}).get("Arn"),
            ""  # Hosted Services (Airflow, APIs, etc.)
        ])

# ---------- POPULATE LAMBDA ----------
with open("collect/lambda.json") as f:
    data = json.load(f)

for fn in data["Functions"]:
    lambda_ws.append([
        "",  # Environment (fill via tag or manually)
        fn["FunctionName"],
        fn["Runtime"],
        fn["Timeout"],
        fn["Role"],
        "", "", ""
    ])

# ---------- POPULATE S3 ----------
with open("collect/s3.json") as f:
    data = json.load(f)

for b in data["Buckets"]:
    s3_ws.append([
        "",  # Env
        b["Name"],
        "", "", "", "", ""
    ])

# ---------- POPULATE SQS ----------
with open("collect/sqs.json") as f:
    data = json.load(f)

for q in data.get("QueueUrls", []):
    sqs_ws.append([
        "", q.split("/")[-1], "", "", "", "", ""
    ])

# ---------- POPULATE CLOUDWATCH ----------
with open("collect/cloudwatch.json") as f:
    data = json.load(f)

for a in data["MetricAlarms"]:
    cw_ws.append([
        "", a["AlarmName"], a["MetricName"],
        a.get("Threshold"), "", ""
    ])

wb.save("resources_inventory.xlsx")
print("Excel workbook created: resources_inventory.xlsx")
