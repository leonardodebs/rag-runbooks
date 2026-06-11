# Checklist do Engenheiro de Plantão e Procedimentos de Escalonamento

## Objetivo
Guia de referência para o engenheiro de plantão (on-call) sobre como receber,
triar, responder e escalar incidentes de produção.

## 1. Início do plantão (handoff)
Ao assumir o plantão:
- Confirme que recebe os alertas (PagerDuty/Opsgenie) fazendo um teste.
- Leia o relatório de passagem do plantonista anterior: incidentes em aberto,
  alertas ruidosos conhecidos, deploys recentes e janelas de manutenção agendadas.
- Verifique se o ambiente está saudável nos dashboards principais.
- Tenha em mãos: acesso ao console, VPN, runbooks e os contatos de escalonamento.

## 2. Ao receber um alerta
Siga o fluxo de triagem:

1. **Reconheça (ack)** o alerta em até 5 minutos para evitar re-escalonamento.
2. **Avalie a severidade** e o impacto: quantos usuários afetados? Há perda de
   dados? Receita parada? Use a matriz de severidade abaixo.
3. **Comunique**: abra um canal de incidente e poste um resumo inicial. Comunicação
   cedo e frequente é melhor que silêncio.
4. **Investigue** usando o runbook específico do sistema afetado.
5. **Mitigue** primeiro, encontre a causa raiz depois. Rollback é uma mitigação
   válida e rápida.

## 3. Matriz de severidade
- **SEV1 (Crítico)**: indisponibilidade total ou perda de dados. Resposta imediata,
  acione o Incident Commander, comunique liderança. Exemplos: site fora, banco
  corrompido, vazamento de segurança.
- **SEV2 (Alto)**: funcionalidade principal degradada para muitos usuários.
  Resposta em até 30 minutos.
- **SEV3 (Médio)**: problema com workaround disponível ou impacto limitado.
  Resposta no próximo horário comercial.
- **SEV4 (Baixo)**: cosmético ou sem impacto a usuário. Vira um ticket no backlog.

## 4. Quando e como escalar
Escale quando:
- Você não consegue mitigar em 30 minutos para um SEV1/SEV2.
- O incidente está fora da sua área de conhecimento.
- É necessária uma decisão acima da sua alçada (ex: comunicar clientes, gastar em
  recursos emergenciais).

Caminho de escalonamento:
1. Engenheiro de plantão (você)
2. Plantonista secundário / especialista do time dono do serviço
3. Líder técnico / engenheiro sênior de plantão
4. Gerente de engenharia / Incident Commander
5. Liderança executiva (apenas SEV1 com impacto a negócio)

Ao escalar, forneça: o que está acontecendo, o impacto, o que você já tentou e o que
precisa da pessoa escalada. Não apenas "está quebrado".

## 5. Durante o incidente
- Mantenha um único canal de comunicação como fonte da verdade.
- Designe papéis em incidentes grandes: Incident Commander (coordena), Operador
  (executa ações), Comunicador (atualiza stakeholders).
- Registre a timeline de ações com horários — será essencial no post-mortem.
- Evite fazer múltiplas mudanças simultâneas; mude uma coisa e observe o efeito.

## 6. Encerramento e pós-incidente
- Confirme que o serviço está estável e as métricas normalizaram antes de declarar
  resolvido.
- Escreva o relatório de passagem se o plantão terminar com algo em aberto.
- Agende um post-mortem blameless para todo SEV1 e SEV2 em até 48 horas.
- Crie itens de ação rastreáveis para evitar recorrência.

## Lembrete
Sua saúde importa. Se um incidente longo esgotar você, peça rendição. Decisões
tomadas exausto causam mais incidentes.
