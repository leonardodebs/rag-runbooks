# Diagnóstico e Resolução de Problemas em Instâncias EC2

## Objetivo
Este runbook descreve como diagnosticar e corrigir problemas comuns em instâncias
EC2 relacionados a CPU, memória, disco e rede. Use-o quando uma instância estiver
lenta, indisponível ou apresentando comportamento anômalo.

## Pré-requisitos
- Acesso ao Console AWS e à AWS CLI configurada
- Permissões de EC2, CloudWatch e Systems Manager (SSM)
- Identificar o `instance-id` afetado antes de começar

## 1. Problemas de CPU alta
Verifique a métrica `CPUUtilization` no CloudWatch para a instância. Se a CPU estiver
acima de 90% de forma sustentada por mais de 15 minutos, conecte via SSM Session
Manager e execute `top` ou `htop` para identificar o processo culpado.

Causas comuns:
- Processo em loop infinito ou vazamento de threads
- Picos legítimos de tráfego exigindo escalonamento horizontal
- Instâncias da família T (burstable) que esgotaram os CPU Credits

Para instâncias T2/T3/T4g, confira a métrica `CPUCreditBalance`. Se estiver zerada,
a instância sofre throttling. Considere habilitar o modo Unlimited ou migrar para
uma família M ou C com performance fixa.

## 2. Problemas de memória
A memória RAM não é exposta nativamente no CloudWatch. Instale o CloudWatch Agent
para coletar `mem_used_percent`. Em uma instância Linux, use `free -h` e `vmstat 1`
para inspecionar uso e swap. Se o swap estiver sendo usado intensamente, a instância
está sob pressão de memória.

Ações recomendadas:
- Identifique processos com `ps aux --sort=-%mem | head`
- Reinicie serviços com vazamento de memória conhecido
- Faça upgrade do tipo de instância para uma com mais RAM
- Configure limites de memória adequados em containers

## 3. Problemas de disco
Verifique o uso com `df -h` e os inodes com `df -i`. Discos cheios causam falhas
silenciosas em logs e bancos de dados. Limpe arquivos de log antigos em `/var/log`
e use `du -sh /*` para localizar diretórios grandes.

Para volumes EBS, monitore `VolumeQueueLength` e `BurstBalance` (em volumes gp2).
Se o BurstBalance chegar a zero, o volume sofre throttling de IOPS. Migre para gp3,
que oferece IOPS provisionados independentes do tamanho.

Para expandir um volume sem downtime: modifique o tamanho no Console EC2, depois
execute `growpart` e `resize2fs` (ext4) ou `xfs_growfs` (xfs) dentro da instância.

## 4. Problemas de rede
Se a instância não responde a SSH, verifique nesta ordem:
- Security Group permite a porta 22 do seu IP de origem
- Network ACL da subnet não está bloqueando o tráfego
- A instância tem IP público ou você está acessando via VPN/bastion
- A tabela de rotas da subnet aponta para um Internet Gateway ou NAT

Use os logs de VPC Flow Logs para confirmar se os pacotes estão chegando. A métrica
`StatusCheckFailed` indica se o problema é de sistema (infraestrutura AWS) ou de
instância (sistema operacional). Falhas de system check exigem stop/start para
migrar para outro hardware físico.

## Escalonamento
Se após esses passos o problema persistir, abra um caso no AWS Support com o
`instance-id`, os logs coletados e o intervalo de tempo do incidente.
