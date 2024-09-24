import json
import requests
import uuid
import argparse

import boto3

'''
    This script is intended to be run from inside the service container.
    What it does:
        Register entrypoint:
            1. It will automatically create a target group for the instance that
               points to the exposed port. (tg-{ec2-instanceid}).
            2. Registers the target group w/ the Load Balancer listener at 
               /container/{ec2-instance-id}.
        Cleanup entrypoing:
            1. Removes the listener based on the priority it created it with.
            2. Deregister the ec2 instance from the Target Group.
            3. Deletes the target group.

    Required perms on Task execution role:
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:CreateTargetGroup",
        "elasticloadbalancing:DeleteTargetGroup",
        "elasticloadbalancing:RegisterTargets",
        "elasticloadbalancing:DeregisterTargets",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:DescribeRules",
        "elasticloadbalancing:CreateRule",
        "elasticloadbalancing:DeleteRule",
        "elasticloadbalancing:SetSubnets",
        "elasticloadbalancing:DescribeLoadBalancers"

        (Potentially)
        "ec2:DescribeInstances",
        "ec2:DescribeSubnets",
        "ec2:DescribeAvailabilityZones"
'''

CONTAINER_PORT = 3006
ALB_ARN = 'arn:aws:elasticloadbalancing:us-east-1:767397907233:loadbalancer/app/test-deploy-lb/3f9b3cd35fdc4474'
LISTENER_ARN = 'arn:aws:elasticloadbalancing:us-east-1:767397907233:listener/app/test-deploy-lb/3f9b3cd35fdc4474/cadd34d71b3a7603' # The listerer that all the tg's will go under.

VPC_ID = 'vpc-038828d46c2c0399a' # FROM ec2 instance
ENDPOINT_BASE_PATH = '/containers'

elb_client = boto3.client('elbv2')


def register_container():
    # Get instance ID
    container_id = str(uuid.uuid4())
    instance_id = requests.get(
        'http://169.254.169.254/latest/meta-data/instance-id').text
    print("Instance ID: ", instance_id)

    # Check if target group for /containers already exists
    target_groups = elb_client.describe_target_groups(
        LoadBalancerArn=ALB_ARN)['TargetGroups']
    target_group_name = f'tg-{instance_id[:8]}'
    target_group_arn = None

    for tg in target_groups:
        if tg['TargetGroupName'] == target_group_name:
            target_group_arn = tg['TargetGroupArn']
            print(f"Target group {target_group_name} already exists.")
            break

    # If the target group doesn't exist, create it
    if not target_group_arn:
        response = elb_client.create_target_group(Name=target_group_name,
                                                  Protocol='HTTP',
                                                  Port=CONTAINER_PORT,
                                                  VpcId=VPC_ID,
                                                  TargetType='instance',
                                                  HealthCheckProtocol='HTTP',
                                                  HealthCheckPort=f'{CONTAINER_PORT}',
                                                  HealthCheckPath='/',
                                                  Matcher={'HttpCode': '200'})
        target_group_arn = response['TargetGroups'][0]['TargetGroupArn']
        print(f"Created new target group: {target_group_name}")

    # List the current rules on the listener
    listener_rules = elb_client.describe_rules(
        ListenerArn=LISTENER_ARN)['Rules']

    # Find unique priority for the new rule (use max priority + 1)
    priorities = [
        int(rule['Priority']) for rule in listener_rules
        if rule['Priority'] != 'default'
    ]
    new_priority = int(max(priorities) + 1) if priorities else '1'

    # Register the EC2 instance with the target group
    elb_client.register_targets(
        TargetGroupArn=target_group_arn,
        Targets=[{
            'Id': instance_id,
            'Port': CONTAINER_PORT
        }
                 ])
    print(
        f"Instance {instance_id} registered with target group {target_group_name}."
    )

    # Create a listener rule for the path /containers/{instance_id}
    path_pattern = f'{ENDPOINT_BASE_PATH}/{instance_id}'

    elb_client.create_rule(ListenerArn=LISTENER_ARN,
                           Conditions=[{
                               'Field': 'path-pattern',
                               'Values': [path_pattern]
                           }],
                           Priority=new_priority,
                           Actions=[{
                               'Type': 'forward',
                               'TargetGroupArn': target_group_arn
                           }])
    print(
        f"Created listener rule for path {path_pattern} with priority {new_priority}."
    )

    return {
        'status': 'success',
        'path': path_pattern,
        'target_group': target_group_name,
        'instance_id': instance_id,
        'rule_priority': new_priority,
        'target_group_arn': target_group_arn
    }


def cleanup(instance_id, rule_priority, target_group_arn):
    """
    Cleans up the created listener rule and target group.
    """
    path_pattern = f'{ENDPOINT_BASE_PATH}/{instance_id}'

    print(
        f"Cleaning up listener rule for path {path_pattern} and target group {target_group_arn}..."
    )

    # Find and delete the rule with the specified priority
    listener_rules = elb_client.describe_rules(
        ListenerArn=LISTENER_ARN)['Rules']

    for rule in listener_rules:
        if int(rule['Priority']) == rule_priority:
            elb_client.delete_rule(RuleArn=rule['RuleArn'])
            print(f"Deleted listener rule for priority {rule_priority}")
            break

    # Deregister targets from the target group
    instance_id = requests.get(
        'http://169.254.169.254/latest/meta-data/instance-id').text
    elb_client.deregister_targets(TargetGroupArn=target_group_arn,
                                  Targets=[{
                                      'Id': instance_id
                                  }])
    print(
        f"Deregistered instance {instance_id} from target group {target_group_arn}"
    )

    # Delete the target group
    elb_client.delete_target_group(TargetGroupArn=target_group_arn)
    print(f"Deleted target group {target_group_arn}")

    print("Cleanup completed.")


def main():
    parser = argparse.ArgumentParser(
        description="Register or cleanup an EC2 task with ALB")

    # Arguments
    parser.add_argument('action',
                        choices=['register', 'cleanup'],
                        help="Action to perform: register or cleanup")
    parser.add_argument('--instance_id',
                        help="EC2 instance ID (needed for cleanup)")
    parser.add_argument('--rule_priority',
                        help="Rule priority (needed for cleanup)")
    parser.add_argument('--target_group_arn',
                        help="Target group ARN (needed for cleanup)")

    args = parser.parse_args()

    metadata_file = '/tmp/rule-metadata.json'

    if args.action == 'register':
        result_metadata = register_container()
        print(f"Register result: {result_metadata}")
        with open(metadata_file, 'w') as f:
            f.write(json.dumps(result_metadata))

    elif args.action == 'cleanup':
        if not args.instance_id or not args.rule_priority or not args.target_group_arn:
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.loads(f.read())

                    # Get the settings for when the run was registered from metadata.
                    args.instance_id = metadata['instance_id']
                    args.rule_priority = metadata['rule_priority']
                    args.target_group_arn = metadata['target_group_arn']
            except FileNotFoundError:
                print(
                    'Metadata file not found. Either pass cli args or run register() first.'
                )
                print(
                    "For cleanup, you must specify --instance_id, --rule_priority, and --target_group_arn."
                )
                return

        print('Running cleanup. . .')
        cleanup(args.instance_id, args.rule_priority, args.target_group_arn)


if __name__ == "__main__":

    main()

