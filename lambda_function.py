import json
import boto3

def handler(event, context):
    kinesis_client = boto3.client('kinesis')
    stream_name = "LogDataStream"

    logs = [
        {"message": "ERROR: High CPU usage detected"},
        {"message": "WARNING: Disk space running low"},
    ]

    for log in logs:
        kinesis_client.put_record(
            StreamName=stream_name,
            Data=json.dumps(log),
            PartitionKey="partitionKey"
        )
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
