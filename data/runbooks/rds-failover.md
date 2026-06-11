# Procedimento de Failover RDS Multi-AZ e Recuperação Point-in-Time

## Objetivo
Descrever como executar e validar um failover em uma instância RDS Multi-AZ e como
realizar a recuperação point-in-time (PITR) após perda ou corrupção de dados.

## Contexto sobre Multi-AZ
Em uma configuração Multi-AZ, a AWS mantém uma réplica standby síncrona em outra
Zona de Disponibilidade. Em caso de falha da instância primária, o RDS promove
automaticamente a standby. O endpoint DNS é atualizado, então a aplicação deve
sempre se conectar pelo endpoint do cluster, nunca pelo IP.

## 1. Failover manual planejado
Use um failover manual para testar a resiliência ou antes de manutenção:

1. No Console RDS, selecione a instância e escolha "Reboot with failover", ou
   execute `aws rds reboot-db-instance --db-instance-identifier nome --force-failover`.
2. O DNS leva tipicamente de 60 a 120 segundos para apontar para a nova primária.
3. A aplicação verá erros de conexão durante esse intervalo. Garanta que o pool de
   conexões tenha retry com backoff exponencial configurado.

Monitore o evento `Multi-AZ failover started` e `completed` na aba Events do RDS.

## 2. Failover automático
O failover automático é disparado por: falha de hardware da primária, perda de
conectividade de rede da AZ, falha no storage ou durante patching do sistema
operacional. Você não precisa intervir, mas deve monitorar a métrica
`DatabaseConnections` para confirmar que a aplicação reconectou.

## 3. Validação pós-failover
Após qualquer failover, valide:
- A aplicação reconectou e processa transações normalmente
- A métrica `ReplicaLag` voltou a um valor próximo de zero na nova standby
- Não há transações pendentes ou locks órfãos
- Os logs de aplicação não mostram erros persistentes de conexão

## 4. Recuperação Point-in-Time (PITR)
O RDS faz backup automático com retenção configurável (1 a 35 dias) e captura logs
de transação a cada 5 minutos. Isso permite restaurar para qualquer segundo dentro
da janela de retenção.

Para restaurar:
1. No Console RDS, selecione a instância e escolha "Restore to point in time".
2. Especifique a data e hora exatas (em UTC) anteriores ao incidente.
3. O RDS cria uma NOVA instância — ele nunca sobrescreve a original.
4. Aguarde a nova instância ficar `available` (pode levar de minutos a horas).
5. Aponte a aplicação para o novo endpoint ou renomeie as instâncias.

Comando CLI de exemplo:
`aws rds restore-db-instance-to-point-in-time --source-db-instance-identifier prod
--target-db-instance-identifier prod-restored --restore-time 2025-06-09T14:30:00Z`

## 5. Cuidados importantes
- A nova instância restaurada começa com Security Groups e parameter groups padrão;
  reconfigure-os antes de liberar tráfego.
- PITR não inclui mudanças feitas após o `restore-time` escolhido.
- Sempre valide a integridade dos dados antes de promover a instância restaurada
  para produção.

## Escalonamento
Se o failover automático não ocorrer ou a instância ficar presa em `failed`, abra
um caso urgente no AWS Support com severidade Production.
