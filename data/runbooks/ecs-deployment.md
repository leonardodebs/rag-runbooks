# Deploy e Rollback de Serviços ECS

## Objetivo
Procedimento para realizar deploy de um serviço ECS (Fargate ou EC2) e como fazer
rollback de forma segura quando uma nova versão apresenta problemas.

## Conceitos básicos
- **Task Definition**: o blueprint do container (imagem, CPU, memória, variáveis).
  Cada alteração gera uma nova revisão (ex: `meu-app:42`).
- **Service**: mantém um número desejado de tasks rodando e gerencia o deploy.
- **Deployment**: o processo de substituir tasks antigas por novas.

## 1. Realizando um deploy
O fluxo padrão de deploy:

1. Faça build da imagem e push para o Amazon ECR com uma tag única (use o SHA do
   commit, nunca apenas `latest`).
2. Registre uma nova revisão da Task Definition apontando para a nova imagem:
   `aws ecs register-task-definition --cli-input-json file://task-def.json`
3. Atualize o serviço para usar a nova revisão:
   `aws ecs update-service --cluster prod --service meu-app --task-definition meu-app:42`
4. O ECS inicia novas tasks e, conforme ficam saudáveis no Target Group, drena e
   encerra as antigas.

## 2. Estratégia de deploy rolling update
O deployment controller padrão é o rolling update, controlado por dois parâmetros:
- `minimumHealthyPercent` (padrão 100%): quantas tasks devem permanecer rodando.
- `maximumPercent` (padrão 200%): quantas tasks podem existir simultaneamente.

Com 100%/200%, o ECS sobe todas as novas antes de derrubar as antigas — zero
downtime, mas dobra o uso de recursos durante o deploy. Para clusters com recursos
limitados, use 50%/100%, aceitando capacidade reduzida temporariamente.

## 3. Como fazer rollback
Se a nova versão falha (erros 5xx, crash loop, health check falhando), o rollback é
simplesmente apontar o serviço de volta para a revisão anterior conhecida como boa:

`aws ecs update-service --cluster prod --service meu-app --task-definition meu-app:41`

O ECS executa o mesmo rolling update, agora substituindo as tasks ruins (42) pelas
boas (41). Sempre anote o número da última revisão estável ANTES de cada deploy.

Para automação, configure o **Deployment Circuit Breaker** com `rollback: true`. O
ECS detecta automaticamente um deploy que não estabiliza e reverte sozinho para a
última revisão saudável, sem intervenção manual.

## 4. Diagnóstico de deploy travado
Se o deploy não progride:
- Verifique os eventos do serviço: `aws ecs describe-services --cluster prod
  --services meu-app` e leia a seção `events`.
- Causas comuns: capacidade insuficiente no cluster, task falhando no health check,
  imagem inexistente no ECR, ou falta de permissão na Task Execution Role.
- Veja os logs da task que falhou no CloudWatch Logs (grupo configurado no
  `logConfiguration` da Task Definition).
- `STOPPED` tasks trazem um `stoppedReason` que indica OOM, exit code ou erro de pull.

## 5. Boas práticas
- Sempre use tags imutáveis de imagem (SHA do commit).
- Mantenha pelo menos as 5 últimas Task Definitions para rollback rápido.
- Configure health checks no container além dos do Target Group.
- Habilite o Circuit Breaker em todos os serviços de produção.

## Escalonamento
Se o rollback não estabilizar o serviço, verifique dependências externas (banco,
filas, APIs) antes de escalar para o time de infraestrutura.
