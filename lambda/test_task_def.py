import boto3
import json
from dotenv import load_dotenv


config = dotenv_values()


CLUSTER = "ApiCluster"
TASK_DEF = {
    "family":
    "ApiTask",
    "containerDefinitions": [{
        "name":
        "fastapi",
        "image":
        f"{config["ECR"]}/api:latest",
        "cpu":
        0,
        "portMappings": [{
            "name": "fapi_port",
            "containerPort": 8000,
            "hostPort": 8000,
            "protocol": "tcp",
            "appProtocol": "http"
        }],
        "essential":
        True,
        "command":
        ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"],
        "environment": [],
        "mountPoints": [],
        "volumesFrom": [],
        "logConfiguration": {
            "logDriver": "awslogs",
            "options": {
                "awslogs-group": "/ecs/ApiTask",
                "mode": "non-blocking",
                "awslogs-create-group": "true",
                "max-buffer-size": "25m",
                "awslogs-region": "us-east-2",
                "awslogs-stream-prefix": "ecs"
            },
            "secretOptions": []
        },
        "systemControls": []
    }],
    "taskRoleArn":
    config["TaskRoleARN"],
    "executionRoleArn":
    config["ExecutionRoleARN"],
    "networkMode":
    "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu":
    "1024",
    "memory":
    "3072",
    "runtimePlatform": {
        "cpuArchitecture": "X86_64",
        "operatingSystemFamily": "LINUX"
    }
}


def lambda_handler(event, context):
    # Initialize ECS client
    ecs_client = boto3.client('ecs')

    # Define the task definition

    try:
        # Register the task definition
        response = ecs_client.register_task_definition(**TASK_DEF)

        # Extract the task definition ARN
        task_definition_arn = response['taskDefinition']['taskDefinitionArn']

        # Run the task
        run_task_response = ecs_client.run_task(
            cluster=CLUSTER,
            taskDefinition=task_definition_arn,
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': ['subnet-0c263b5966df1bb3b'],
                    'securityGroups': ['sg-0e15fa946424f868b'],
                    'assignPublicIp': 'ENABLED'
                }
            })

        return {
            'statusCode': 200,
            'body': json.dumps('Task deployed successfully!')
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error deploying task: {str(e)}')
        }

