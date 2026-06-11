# Playbook de Resposta a Incidentes de Segurança

## Objetivo
Procedimento de resposta a incidentes de segurança na AWS, cobrindo achados do
GuardDuty, comprometimento de credenciais IAM e contenção inicial.

## Princípios gerais
A resposta segue quatro fases: **Detecção**, **Contenção**, **Erradicação** e
**Recuperação**. Priorize a contenção sobre a investigação — primeiro estanque o
sangramento, depois entenda a causa. Documente cada ação com timestamp para o
relatório pós-incidente (post-mortem).

## 1. Triagem de achados do GuardDuty
O GuardDuty gera findings com severidade de 0 a 8.9. Trate primeiro os de
severidade alta (7.0+). Findings comuns e suas implicações:

- `UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration`: credenciais de uma
  role de EC2 foram usadas de fora da AWS. Indica vazamento de credenciais.
- `CryptoCurrency:EC2/BitcoinTool.B`: a instância pode estar minerando cripto após
  comprometimento.
- `Recon:IAMUser/MaliciousIPCaller`: chamadas de API a partir de IP malicioso
  conhecido.
- `UnauthorizedAccess:IAMUser/ConsoleLoginSuccess.B`: login bem-sucedido de IP
  suspeito ou geografia incomum.

## 2. Comprometimento de credenciais IAM
Se uma chave de acesso (access key) foi exposta:

1. **Desative imediatamente** a chave: `aws iam update-access-key
   --access-key-id AKIA... --status Inactive`. Desativar é reversível; deletar não.
2. Revise o CloudTrail para mapear todas as ações feitas com aquela credencial nas
   últimas horas/dias. Procure por `CreateUser`, `AttachUserPolicy`, `CreateAccessKey`.
3. Procure por backdoors: novos usuários IAM, novas chaves, policies anexadas,
   roles criadas, ou trust policies modificadas.
4. Após confirmar que a aplicação legítima migrou para uma nova credencial, delete
   a chave comprometida.
5. Rotacione TODAS as credenciais relacionadas por precaução.

## 3. Contenção de instância EC2 comprometida
Para uma instância suspeita de comprometimento:

1. **Não desligue a instância** — isso destrói evidências em memória. Isole-a.
2. Crie um Security Group de quarentena sem regras de saída (egress) e aplique-o à
   instância, cortando comunicação com o atacante.
3. Tire um snapshot do volume EBS para análise forense posterior.
4. Capture metadados: processos em execução, conexões de rede ativas, usuários
   logados — se conseguir acesso seguro via SSM.
5. Remova a instância do Target Group / Auto Scaling Group para parar de receber
   tráfego de produção.

## 4. Erradicação e recuperação
- Remova todos os artefatos do atacante (backdoors, cron jobs, chaves SSH).
- Reconstrua a instância a partir de uma AMI limpa e confiável — não tente
  "limpar" um host comprometido para retornar à produção.
- Aplique patches e feche o vetor de entrada original.
- Habilite MFA em todas as contas privilegiadas.

## 5. Pós-incidente
Conduza um post-mortem sem culpabilização (blameless). Documente a timeline, o
impacto, a causa raiz e os itens de ação preventivos. Atualize este runbook com o
que foi aprendido.

## Escalonamento
Incidentes de severidade alta devem ser escalados imediatamente para o time de
segurança e, se houver dados de clientes envolvidos, para o jurídico e compliance.
