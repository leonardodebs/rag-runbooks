# Troubleshooting de Erros 502 e 503 no Application Load Balancer

## Objetivo
Guia para diagnosticar e resolver erros HTTP 502 (Bad Gateway) e 503 (Service
Unavailable) retornados por um Application Load Balancer (ALB).

## Diferença entre 502 e 503
- **502 Bad Gateway**: o ALB conseguiu encaminhar a requisição para um target, mas
  recebeu uma resposta inválida ou a conexão foi fechada inesperadamente.
- **503 Service Unavailable**: o ALB não tem nenhum target saudável disponível no
  Target Group para atender a requisição.

## 1. Investigando erros 503
O 503 quase sempre significa "não há targets saudáveis". Verifique:

1. No Console EC2 → Target Groups, confira a coluna Health Status dos targets.
2. Se todos estão `unhealthy`, revise a configuração do Health Check: caminho
   (ex: `/health`), porta, código HTTP esperado e timeout.
3. Confirme que a aplicação realmente responde no caminho de health check. Um
   endpoint de health que faz query pesada no banco pode estourar o timeout.
4. Verifique se o Security Group dos targets permite tráfego vindo do Security
   Group do ALB na porta da aplicação.

Ajuste os limiares: `HealthyThresholdCount`, `UnhealthyThresholdCount` e o
`Interval`. Health checks muito agressivos derrubam targets durante picos.

## 2. Investigando erros 502
O 502 indica que o target respondeu de forma inválida. Causas frequentes:

- A aplicação crashou ou reiniciou no meio da resposta
- Timeout de idle do ALB (padrão 60s) menor que o tempo de resposta do backend
- Incompatibilidade de keep-alive: o backend fecha a conexão antes do ALB
- Resposta HTTP malformada ou headers inválidos pela aplicação
- Para HTTPS no backend, certificado expirado ou cadeia incompleta

O ALB Keep-Alive timeout do backend deve ser MAIOR que o idle timeout do ALB. Se o
backend (ex: Nginx, Gunicorn) fecha conexões em 5s e o ALB tenta reusar em 60s,
você verá 502 intermitentes.

## 3. Usando os Access Logs do ALB
Habilite os Access Logs do ALB (gravados em S3). Cada linha contém o campo
`elb_status_code` e `target_status_code`. Quando `elb_status_code` é 502 e
`target_status_code` é "-", o target não enviou resposta válida. O campo
`target_processing_time` ajuda a identificar timeouts.

## 4. Métricas no CloudWatch
Monitore estas métricas do ALB:
- `HTTPCode_ELB_502_Count` e `HTTPCode_ELB_503_Count`
- `HealthyHostCount` e `UnHealthyHostCount` por Target Group
- `TargetResponseTime` para detectar lentidão do backend
- `RejectedConnectionCount` indica esgotamento de capacidade

## 5. Checklist rápido de resolução
1. Há targets saudáveis? (resolve a maioria dos 503)
2. O health check bate no endpoint correto e retorna 200?
3. O idle timeout do ALB é compatível com o keep-alive do backend? (resolve 502)
4. Os Security Groups permitem o tráfego ALB → target?
5. A aplicação está logando erros 5xx internos?

## Escalonamento
Se os targets estão saudáveis e ainda há 502, capture os Access Logs do intervalo
e os logs da aplicação correspondentes e escale para o time de plantão da aplicação.
