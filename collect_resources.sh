#!/bin/bash
set -e

mkdir -p collect

echo "Collecting EC2..."
aws ec2 describe-instances > collect/ec2.json

echo "Collecting Lambda..."
aws lambda list-functions > collect/lambda.json

echo "Collecting S3..."
aws s3api list-buckets > collect/s3.json

echo "Collecting SQS..."
aws sqs list-queues > collect/sqs.json

echo "Collecting CloudWatch Alarms..."
aws cloudwatch describe-alarms > collect/cloudwatch.json

echo "Done."
