import boto3
import datetime
import os

# Initialize boto3 clients
ec2_client = boto3.client('ec2')
cw_client = boto3.client('cloudwatch')
sns_client = boto3.client('sns')

def check_underutilized_instances():
    underutilized_instances = []
    
    # Get all running EC2 instances
    instances = ec2_client.describe_instances(
        Filters=[
            {
                'Name': 'instance-state-name',
                'Values': ['running']
            }
        ]
    )
    
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            
            # Get CPU utilization of the instance over the last 24 hours
            metrics = cw_client.get_metric_data(
                MetricDataQueries=[
                    {
                        'Id': 'm1',
                        'MetricStat': {
                            'Metric': {
                                'Namespace': 'AWS/EC2',
                                'MetricName': 'CPUUtilization',
                                'Dimensions': [
                                    {
                                        'Name': 'InstanceId',
                                        'Value': instance_id
                                    }
                                ]
                            },
                            'Period': 3600,  # 1 hour period
                            'Stat': 'Average'
                        },
                        'ReturnData': True
                    }
                ],
                StartTime=datetime.datetime.utcnow() - datetime.timedelta(days=1),
                EndTime=datetime.datetime.utcnow()
            )
            
            # Calculate average CPU utilization over the last 24 hours
            avg_cpu = sum([dp['Value'] for dp in metrics['MetricDataResults'][0]['Values']]) / len(metrics['MetricDataResults'][0]['Values'])
            
            if avg_cpu < 20:  # Threshold: 20%
                underutilized_instances.append(instance_id)
    
    return underutilized_instances

def check_old_amis():
    old_amis = []
    
    # Fetch all AMIs owned by your account
    amis = ec2_client.describe_images(Owners=['self'])
    
    one_year_ago = datetime.datetime.utcnow() - datetime.timedelta(days=365)
    
    for ami in amis['Images']:
        creation_date = datetime.datetime.strptime(ami['CreationDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
        if creation_date < one_year_ago:
            old_amis.append(ami['ImageId'])
    
    return old_amis

def lambda_handler(event, context):
    # Define the SNS topic ARN where messages will be sent
    sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')

    underutilized_instances = check_underutilized_instances()
    old_amis = check_old_amis()

    # If there are underutilized instances or old AMIs, send messages to the SNS topic
    if underutilized_instances:
        message = f"Underutilized EC2 instances: {', '.join(underutilized_instances)}"
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=message,
            Subject='Underutilized EC2 Instances Identified'
        )

    if old_amis:
        ami_message = f"Old AMIs (older than 1 year): {', '.join(old_amis)}"
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=ami_message,
            Subject='Old AMIs Identified'
        )

    return {
        'statusCode': 200,
        'body': f"Identified {len(underutilized_instances)} underutilized instances and {len(old_amis)} old AMIs."
    }
