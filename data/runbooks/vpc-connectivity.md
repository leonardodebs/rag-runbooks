# Troubleshooting de Conectividade em VPC

## Objetivo
Diagnosticar problemas de conectividade dentro de uma VPC, envolvendo Security
Groups, Network ACLs, tabelas de rotas e gateways.

## Modelo mental: camadas de rede
A conectividade na AWS é controlada por múltiplas camadas que devem TODAS permitir
o tráfego. Verifique nesta ordem, da mais comum para a menos comum:
1. Security Groups (nível da instância, com estado)
2. Network ACLs (nível da subnet, sem estado)
3. Tabelas de rotas (para onde o tráfego é encaminhado)
4. Gateways (Internet Gateway, NAT, VPC Peering, Transit Gateway)

## 1. Security Groups
Os Security Groups são **stateful**: se você permite o tráfego de entrada, a
resposta de saída é automaticamente permitida (e vice-versa). Eles só têm regras de
**allow**, nunca de deny.

Verifique:
- A regra de inbound permite a porta e o protocolo corretos da origem esperada.
- A origem pode ser um CIDR ou outro Security Group (recomendado entre recursos).
- Para comunicação entre dois recursos, referencie o SG de origem na regra do SG
  de destino, em vez de usar IPs.

Erro clássico: a aplicação A não conecta no banco B porque o SG de B não permite a
porta 5432 vinda do SG de A.

## 2. Network ACLs
As NACLs são **stateless**: você precisa permitir explicitamente o tráfego de
entrada E o de saída separadamente. O tráfego de resposta usa portas efêmeras
(1024-65535), então sua regra de saída precisa permiti-las.

Verifique:
- Regras de inbound E outbound para o tráfego e a resposta.
- A ordem das regras importa — são avaliadas por número, a primeira que casa vence.
- A regra padrão `*` nega tudo que não casou antes.
- Lembre das portas efêmeras para o tráfego de retorno.

NACLs são uma camada extra; a maioria dos ambientes usa a NACL padrão (permite tudo)
e controla tudo via Security Groups.

## 3. Tabelas de rotas
Cada subnet está associada a uma route table. Verifique:
- Subnet **pública**: tem rota `0.0.0.0/0` apontando para um Internet Gateway (igw-).
- Subnet **privada**: tem rota `0.0.0.0/0` apontando para um NAT Gateway (nat-) para
  acesso de saída à internet.
- Rotas locais (`10.0.0.0/16 → local`) cobrem a comunicação interna da VPC.
- Para VPC Peering ou Transit Gateway, deve haver rotas explícitas para o CIDR remoto.

## 4. Gateways
- **Internet Gateway**: necessário para subnets públicas. A instância também precisa
  de IP público para ser acessível de fora.
- **NAT Gateway**: permite que subnets privadas iniciem conexões de saída sem aceitar
  entrada. Deve ficar em uma subnet pública.
- **VPC Peering**: não é transitivo. Se A peering com B e B com C, A não fala com C.

## 5. Ferramentas de diagnóstico
- **VPC Reachability Analyzer**: simula um caminho entre origem e destino e aponta
  exatamente qual componente bloqueia (SG, NACL ou rota).
- **VPC Flow Logs**: registram ACCEPT/REJECT por fluxo. Um REJECT mostra que uma
  NACL ou SG bloqueou; a ausência de registros indica problema de roteamento.
- `traceroute` e `telnet host porta` de dentro da instância para testes pontuais.

## Escalonamento
Se o Reachability Analyzer indicar caminho válido mas a conexão falha, investigue a
camada de aplicação (firewall do SO, serviço não escutando na porta) antes de escalar.
