
import boto3
import os
from datetime import datetime, timedelta

def lambda_handler(event, context):
    ce_client = boto3.client('ce')
    cw_client = boto3.client('cloudwatch')
    ec2_client = boto3.client('ec2')

    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    print("--- Análise de Custos e Desperdícios da AWS ---")

    # 1. Análise de Custos por Serviço
    try:
        cost_response = ce_client.get_cost_and_usage(
            TimePeriod={'Start': start_date, 'End': end_date},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
        )
        print("\n[Análise de Custos por Serviço (Últimos 30 dias)]")
        for result in cost_response['ResultsByTime'][0]['Groups']:
            cost = float(result['Metrics']['UnblendedCost']['Amount'])
            if cost > 0:
                print(f"- {result['Keys'][0]}: ${cost:.2f}")
    except Exception as e:
        print(f"Erro ao buscar custos: {e}")

    # 2. Métrica 1: Média de Utilização de CPU das Instâncias EC2 (Últimas 24h)
    try:
        print("\n[Métrica 1: Utilização Média de CPU EC2 (24h)]")
        instances = ec2_client.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                metrics = cw_client.get_metric_statistics(
                    Namespace='AWS/EC2',
                    MetricName='CPUUtilization',
                    Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                    StartTime=datetime.now() - timedelta(days=1),
                    EndTime=datetime.now(),
                    Period=86400,
                    Statistics=['Average']
                )
                if metrics['Datapoints']:
                    avg_cpu = metrics['Datapoints'][0]['Average']
                    print(f"- Instância {instance_id}: {avg_cpu:.2f}% de utilização média")
    except Exception as e:
        print(f"Erro ao buscar métricas de CPU do EC2: {e}")

    # 3. Métrica 2 e Desperdício: Volumes EBS Não Utilizados
    try:
        print("\n[Métrica 2 e Desperdício: Volumes EBS Não Utilizados]")
        volumes = ec2_client.describe_volumes(Filters=[{'Name': 'status', 'Values': ['available']}])
        if volumes['Volumes']:
            for volume in volumes['Volumes']:
                print(f"- Volume {volume['VolumeId']} (Tamanho: {volume['Size']}GB) está disponível e não anexado. Custo potencial de desperdício.")
        else:
            print("- Nenhum volume EBS não utilizado encontrado.")
    except Exception as e:
        print(f"Erro ao buscar volumes EBS: {e}")

    print("\n--- Fim da Análise ---")

    return {
        'statusCode': 200,
        'body': 'Análise concluída. Verifique os logs do CloudWatch.'
    }
