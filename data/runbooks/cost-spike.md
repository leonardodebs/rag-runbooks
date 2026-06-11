# Investigação e Redução de Picos de Custo na AWS

## Objetivo
Como investigar um aumento inesperado na fatura da AWS, identificar a causa raiz e
aplicar medidas de redução de custo.

## 1. Primeiros passos no Cost Explorer
Comece pelo AWS Cost Explorer para localizar a origem do pico:

1. Agrupe os custos por **Service** para ver qual serviço cresceu (EC2, S3, RDS,
   Data Transfer, etc.).
2. Mude o agrupamento para **Usage Type** dentro do serviço culpado para entender
   a dimensão (horas de instância, GB armazenados, GB transferidos).
3. Use o filtro de **Tag** ou **Linked Account** para isolar a equipe ou ambiente.
4. Compare o período do pico com a semana ou mês anterior para quantificar o delta.

Ative a granularidade diária ou horária para identificar exatamente quando o
aumento começou e correlacionar com deploys ou mudanças de infraestrutura.

## 2. Causas comuns de picos
- **Data Transfer**: tráfego entre AZs, saída para a internet (egress) ou
  NAT Gateway processando muito volume. Transferência cross-region é cara.
- **EC2/RDS esquecidos**: instâncias de teste ligadas sem uso, ou um Auto Scaling
  Group que escalou e não reduziu.
- **S3**: requests excessivos (GET/PUT), versionamento acumulando objetos antigos,
  ou ausência de lifecycle policies.
- **CloudWatch Logs**: ingestão massiva de logs por aplicação verbosa.
- **Snapshots órfãos**: EBS snapshots antigos nunca deletados.
- **Recursos sem tag**: dificultam a atribuição e costumam esconder desperdício.

## 3. Reduzindo custo de NAT Gateway e Data Transfer
O NAT Gateway cobra por hora E por GB processado. Se o tráfego de saída é alto:
- Use VPC Endpoints (Gateway) para S3 e DynamoDB — eliminam o NAT para esses
  serviços e são gratuitos.
- Coloque recursos que conversam muito na mesma AZ para evitar custo cross-AZ.
- Para tráfego de saída legítimo alto, avalie um NAT Instance ou revise a
  arquitetura.

## 4. Otimizações estruturais
- **Savings Plans / Reserved Instances**: para workloads estáveis, comprometa-se a
  1 ou 3 anos e economize até 72% versus on-demand.
- **Right-sizing**: use o AWS Compute Optimizer para identificar instâncias
  superdimensionadas e reduza o tipo.
- **Spot Instances**: para cargas tolerantes a interrupção (batch, CI), economize
  até 90%.
- **S3 Intelligent-Tiering**: move objetos automaticamente para camadas mais
  baratas conforme o acesso diminui.
- **Lifecycle policies**: expire logs e versões antigas automaticamente.

## 5. Prevenção contínua
- Configure **AWS Budgets** com alertas por e-mail quando o gasto previsto exceder
  um limite.
- Habilite **Cost Anomaly Detection** para receber alertas automáticos de desvios.
- Adote uma política de tagueamento obrigatório para rastrear custo por time.
- Revise mensalmente o relatório de custos com os times responsáveis.

## Escalonamento
Se o pico indicar uso não autorizado (ex: mineração de cripto após comprometimento),
trate como incidente de segurança e siga o playbook correspondente.
