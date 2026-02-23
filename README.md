# Analisador de Custos e Desperdícios na AWS

Esta solução implementa uma função AWS Lambda para analisar os custos da sua conta, identificar métricas de utilização e apontar potenciais desperdícios, como volumes EBS não utilizados. Os resultados são exibidos de forma clara e organizada nos logs do CloudWatch.

## Funcionalidades

1.  **Análise de Custos por Serviço:** Exibe os custos não combinados (`UnblendedCost`) dos últimos 30 dias, agrupados por serviço.
2.  **Métrica de Utilização de CPU:** Calcula a utilização média de CPU para todas as instâncias EC2 em execução nas últimas 24 horas.
3.  **Identificação de Desperdício:** Lista todos os volumes EBS com o status `available`, que não estão anexados a nenhuma instância e representam um custo potencial sem uso.

## Arquivos do Projeto

-   `src/main.py`: O código-fonte da função Lambda em Python 3.9.
-   `template.yaml`: O template do AWS CloudFormation para criar a infraestrutura necessária (Role IAM e Função Lambda).

## Passos para Deploy

Siga os passos abaixo para implantar a solução em sua conta da AWS.

### 1. Criar o Pacote de Deploy

Navegue até o diretório `src` e crie um arquivo ZIP contendo o código da função:

```bash
cd /home/ubuntu/aws-cost-and-waste-analyzer/src
zip ../cost-and-waste-analyzer.zip main.py
cd ..
```

### 2. Fazer Upload para o S3

Faça o upload do arquivo `cost-and-waste-analyzer.zip` para um bucket S3 de sua escolha. Este bucket será usado pelo CloudFormation para o deploy.

```bash
aws s3 cp cost-and-waste-analyzer.zip s3://SEU-BUCKET-S3/
```

*Substitua `SEU-BUCKET-S3` pelo nome do seu bucket.*

### 3. Fazer o Deploy da Stack do CloudFormation

Utilize o AWS CLI para fazer o deploy da stack. Você precisará fornecer o nome do bucket S3 como um parâmetro.

```bash
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name CostAndWasteAnalyzerStack \
  --parameter-overrides S3BucketName=SEU-BUCKET-S3 \
  --capabilities CAPABILITY_NAMED_IAM
```

*Substitua `SEU-BUCKET-S3` pelo nome do seu bucket.*

## Visualizando os Resultados

Após a conclusão do deploy, a função Lambda pode ser invocada manualmente ou por um gatilho (ex: EventBridge). Para visualizar a análise:

1.  Acesse o console da AWS e navegue até o serviço **CloudWatch**.
2.  No menu à esquerda, vá para **Logs > Grupos de logs**.
3.  Encontre e clique no grupo de logs `/aws/lambda/CostAndWasteAnalyzerFunction`.
4.  Selecione o stream de log mais recente para ver o output detalhado da análise.

### Exemplo de Saída no Log

```
--- Análise de Custos e Desperdícios da AWS ---

[Análise de Custos por Serviço (Últimos 30 dias)]
- Amazon Elastic Compute Cloud - EC2: $150.75
- Amazon Simple Storage Service: $25.50
- AWS Key Management Service: $1.00

[Métrica 1: Utilização Média de CPU EC2 (24h)]
- Instância i-0123456789abcdef0: 5.25% de utilização média
- Instância i-fedcba9876543210f: 22.80% de utilização média

[Métrica 2 e Desperdício: Volumes EBS Não Utilizados]
- Volume vol-0abcdef1234567890 (Tamanho: 20GB) está disponível e não anexado. Custo potencial de desperdício.

--- Fim da Análise ---
```
