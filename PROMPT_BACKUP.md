# Prompt de Reconstrução e Análise da Solução: Analisador de Custos AWS

Este documento serve como um backup completo e um guia detalhado para a reconstrução, análise e evolução da solução "Analisador de Custos e Desperdícios na AWS". O objetivo é que um agente de IA ou um desenvolvedor possa compreender 100% da solução a partir deste prompt.

---

## 1. Objetivo Principal

O objetivo desta solução é criar uma função AWS Lambda, totalmente automatizada e implantável via Infraestrutura como Código (IaC), que analisa uma conta da AWS para extrair informações sobre custos, métricas de uso e identificar recursos desperdiçados. O resultado da análise deve ser formatado de maneira clara e concisa e enviado para os logs do Amazon CloudWatch para fácil visualização e auditoria.

---

## 2. Requisitos Funcionais e Regras de Negócio

A solução deve executar três análises distintas e independentes a cada execução:

1.  **Análise de Custos por Serviço:**
    *   **Fonte de Dados:** AWS Cost Explorer API (`get_cost_and_usage`).
    *   **Período:** Deve analisar os últimos 30 dias a partir da data de execução.
    *   **Métrica:** Utilizar `UnblendedCost`.
    *   **Agrupamento:** Os custos devem ser agrupados por `SERVICE`.
    *   **Regra:** Apenas serviços com custo (`Amount`) maior que zero devem ser exibidos no resultado.

2.  **Métrica de Utilização de Recursos (EC2 CPU):**
    *   **Fonte de Dados:** Amazon CloudWatch Metrics API (`get_metric_statistics`) e EC2 API (`describe_instances`).
    *   **Recursos Alvo:** Todas as instâncias EC2 que estão no estado `running`.
    *   **Métrica:** `CPUUtilization` do namespace `AWS/EC2`.
    *   **Período:** A média de utilização deve ser calculada com base nas últimas 24 horas.
    *   **Estatística:** Utilizar a `Average` (Média).

3.  **Identificação de Desperdício (Volumes EBS):**
    *   **Fonte de Dados:** Amazon EC2 API (`describe_volumes`).
    *   **Recursos Alvo:** Todos os volumes EBS (discos) que estão no estado `available`.
    *   **Regra:** Um volume `available` é considerado um desperdício, pois não está anexado a nenhuma instância EC2 e, portanto, não está em uso, mas continua gerando custos.
    *   **Saída:** Para cada volume encontrado, exibir seu `VolumeId` e `Size` (em GB).

4.  **Formato da Saída (Log):**
    *   A saída no CloudWatch Logs deve ser estruturada com títulos claros para cada uma das três seções de análise.
    *   A formatação deve ser humanamente legível, utilizando hífens e descrições claras para cada item.

---

## 3. Arquitetura da Solução

A solução é composta pelos seguintes componentes da AWS:

*   **AWS Lambda:** O core da solução. Uma função (`CostAndWasteAnalyzerFunction`) escrita em Python 3.9 que contém a lógica de negócio para consultar as APIs da AWS.
*   **IAM Role:** Uma role (`CostAndWasteAnalyzerLambdaRole`) que concede à função Lambda as permissões estritamente necessárias para acessar o Cost Explorer, CloudWatch Metrics e EC2, além de permissão para escrever logs.
*   **Amazon CloudWatch Logs:** O destino da saída da função Lambda. Um grupo de logs (`/aws/lambda/CostAndWasteAnalyzerFunction`) é criado automaticamente para armazenar os resultados de cada execução.
*   **AWS CloudFormation:** Utilizado para orquestrar o deploy de todos os componentes acima de forma declarativa e automatizada a partir de um único template (`template.yaml`).
*   **Amazon S3:** Um bucket S3 (fornecido pelo usuário no momento do deploy) é usado como um repositório temporário para o pacote de código `.zip` da função Lambda.

---

## 4. Estrutura do Projeto

O projeto deve ser organizado na seguinte estrutura de diretórios e arquivos:

```
/aws-cost-and-waste-analyzer
|-- src/
|   `-- main.py
|-- template.yaml
`-- README.md
```

---

## 5. Código-Fonte Completo (`src/main.py`)

O arquivo `main.py` contém toda a lógica da função Lambda.

```python
import boto3
import os
from datetime import datetime, timedelta

def lambda_handler(event, context):
    # Inicializa os clientes dos serviços da AWS
    ce_client = boto3.client("ce")
    cw_client = boto3.client("cloudwatch")
    ec2_client = boto3.client("ec2")

    # Define o período de análise (últimos 30 dias)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    print("--- Análise de Custos e Desperdícios da AWS ---")

    # 1. Análise de Custos por Serviço
    try:
        cost_response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        print("\n[Análise de Custos por Serviço (Últimos 30 dias)]")
        for result in cost_response["ResultsByTime"][0]["Groups"]:
            cost = float(result["Metrics"]["UnblendedCost"]["Amount"])
            if cost > 0:
                print(f"- {result["Keys"][0]}: ${cost:.2f}")
    except Exception as e:
        print(f"Erro ao buscar custos: {e}")

    # 2. Métrica 1: Média de Utilização de CPU das Instâncias EC2 (Últimas 24h)
    try:
        print("\n[Métrica 1: Utilização Média de CPU EC2 (24h)]")
        instances = ec2_client.describe_instances(
            Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
        )
        for reservation in instances["Reservations"]:
            for instance in reservation["Instances"]:
                instance_id = instance["InstanceId"]
                metrics = cw_client.get_metric_statistics(
                    Namespace="AWS/EC2",
                    MetricName="CPUUtilization",
                    Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                    StartTime=datetime.now() - timedelta(days=1),
                    EndTime=datetime.now(),
                    Period=86400, # 24 horas em segundos
                    Statistics=["Average"],
                )
                if metrics["Datapoints"]:
                    avg_cpu = metrics["Datapoints"][0]["Average"]
                    print(f"- Instância {instance_id}: {avg_cpu:.2f}% de utilização média")
    except Exception as e:
        print(f"Erro ao buscar métricas de CPU do EC2: {e}")

    # 3. Métrica 2 e Desperdício: Volumes EBS Não Utilizados
    try:
        print("\n[Métrica 2 e Desperdício: Volumes EBS Não Utilizados]")
        volumes = ec2_client.describe_volumes(
            Filters=[{"Name": "status", "Values": ["available"]}]
        )
        if volumes["Volumes"]:
            for volume in volumes["Volumes"]:
                print(
                    f"- Volume {volume["VolumeId"]} (Tamanho: {volume["Size"]}GB) está disponível e não anexado. Custo potencial de desperdício."
                )
        else:
            print("- Nenhum volume EBS não utilizado encontrado.")
    except Exception as e:
        print(f"Erro ao buscar volumes EBS: {e}")

    print("\n--- Fim da Análise ---")

    return {"statusCode": 200, "body": "Análise concluída. Verifique os logs do CloudWatch."}

```

---

## 6. Infraestrutura como Código (`template.yaml`)

O arquivo `template.yaml` define todos os recursos da AWS necessários.

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: Deploys a Lambda function to analyze AWS costs and waste.

Parameters:
  S3BucketName:
    Type: String
    Description: The name of the S3 bucket where the Lambda deployment package is stored.

Resources:
  CostAndWasteAnalyzerLambdaRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: CostAndWasteAnalyzerLambdaRole
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service:
                - lambda.amazonaws.com
            Action:
              - sts:AssumeRole
      Policies:
        - PolicyName: CostExplorerAndMetricsPolicy
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - ce:GetCostAndUsage
                  - cloudwatch:GetMetricStatistics
                  - ec2:DescribeInstances
                  - ec2:DescribeVolumes
                Resource: "*"
        - PolicyName: LambdaLogsPolicy
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: "arn:aws:logs:*:*:*"

  CostAndWasteAnalyzerLambdaFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: CostAndWasteAnalyzerFunction
      Runtime: python3.9
      Role: !GetAtt CostAndWasteAnalyzerLambdaRole.Arn
      Handler: src.main.lambda_handler
      Code:
        S3Bucket: !Ref S3BucketName
        S3Key: cost-and-waste-analyzer.zip
      Timeout: 120
      MemorySize: 256
```

---

## 7. Instruções de Deploy e Execução

1.  **Empacotar:** `cd src && zip ../cost-and-waste-analyzer.zip main.py && cd ..`
2.  **Upload:** `aws s3 cp cost-and-waste-analyzer.zip s3://SEU-BUCKET-S3/`
3.  **Deploy:** `aws cloudformation deploy --template-file template.yaml --stack-name CostAndWasteAnalyzerStack --parameter-overrides S3BucketName=SEU-BUCKET-S3 --capabilities CAPABILITY_NAMED_IAM`

---

## 8. Comportamento Esperado (Saída no CloudWatch)

A saída no log do CloudWatch deve seguir este formato:

```
--- Análise de Custos e Desperdícios da AWS ---

[Análise de Custos por Serviço (Últimos 30 dias)]
- Amazon Elastic Compute Cloud - EC2: $150.75
- Amazon Simple Storage Service: $25.50

[Métrica 1: Utilização Média de CPU EC2 (24h)]
- Instância i-0123456789abcdef0: 5.25% de utilização média

[Métrica 2 e Desperdício: Volumes EBS Não Utilizados]
- Volume vol-0abcdef1234567890 (Tamanho: 20GB) está disponível e não anexado. Custo potencial de desperdício.

--- Fim da Análise ---
```

---

## 9. Contexto e Decisões de Design

*   **Linguagem:** Python 3.9 foi escolhido por sua simplicidade, vasta biblioteca padrão e excelente suporte na AWS (Boto3), sendo ideal para scripts de automação e interações com APIs.
*   **Simplicidade:** A lógica foi mantida em um único arquivo (`main.py`) para facilitar o entendimento e o deploy, evitando complexidades desnecessárias para a tarefa.
*   **Infraestrutura como Código (IaC):** O uso do CloudFormation garante que a implantação seja repetível, consistente e documentada, evitando configurações manuais e propensas a erros.
*   **Segurança:** A IAM Role segue o princípio do menor privilégio, concedendo apenas as permissões estritamente necessárias para a execução da tarefa.
