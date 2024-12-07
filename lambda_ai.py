import os
import boto3
import json
import base64

# AWS Clients
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime')
ec2_client = boto3.client('ec2')

def handler(event, context):
    # Parse Kinesis event data
    records = event["Records"]
    log_messages = []
    for record in records:
        raw_data = record["kinesis"]["data"]
        decoded_data = base64.b64decode(raw_data)  # Convert Base64 to bytes
        payload = json.loads(decoded_data.decode("utf-8"))  # Convert bytes to string and parse JSON

        log_messages.append(payload["message"])  # Assume log messages are in "message" field

    log_input = " ".join(log_messages)

    # Retrieve the knowledge base from S3
    bucket_name = os.getenv("KNOWLEDGE_BASE_BUCKET")
    knowledge_base_key = "knowledge_base.json"
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=knowledge_base_key)
        knowledge_base = json.loads(response['Body'].read())
    except Exception as e:
        print(f"Error retrieving knowledge base: {e}")
        knowledge_base = {}

    # Prepare input for Bedrock Claude model
    prompt = f"""
    \n\nHuman: The following are logs from a system:
    Logs: {log_input}

    Use the knowledge base below to analyze the logs and recommend actions:
    Knowledge Base: {json.dumps(knowledge_base)}

    Respond with the severity of the issue and recommended action.

    \n\nAssistant:
    """

    # Invoke Bedrock Claude model
    model_id = os.getenv("BEDROCK_MODEL_ID")
    response = bedrock_client.invoke_model(
        modelId=model_id,
        body=json.dumps({"prompt": prompt, "max_tokens_to_sample": 100, "temperature": 0.7}),
        contentType="application/json"
    )

    # Parse Claude's response
    print(f"Invoke model response : {response}")
    #response_body = json.loads(response['body'])
    #analysis = response_body.get("completion", "")
    stream = response.get('body')
    res = []
    if stream:
        for event in stream:
            chunk = event.decode('utf-8')
            if chunk:
                r = json.loads(chunk)
                r = json.dumps(r)
                print(r)
                res.append(r)
    analysis = " ".join(res)

    # Take action based on analysis  
    if "restart" in analysis.lower():
        instance_id =  os.getenv("INSTANCE_ID") # Replace with your EC2 instance ID
        ec2_client.terminate_instances(InstanceIds=[instance_id])
        print(f"EC2 instance {instance_id} terminated due to detected issue.")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "analysis": analysis,
            "actionTaken": "Restarted EC2 instance" if "restart" in analysis.lower() else "No action required"
        })
    }
