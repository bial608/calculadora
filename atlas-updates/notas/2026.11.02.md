# ATLAS — Update 2026.11.02 · Rede automática (sem IP, casas diferentes)

## O que mudou (e por quê)

Você disse o essencial: **não sabe ver IP nem o usuário do Windows, e os PCs
estão em casas diferentes**. A verdade técnica é que SSH sozinho só funciona na
mesma casa. Então troquei a abordagem para algo prático:

**Descoberta automática pelo Tailscale.** Agora o painel **🖧 REDE** acha suas
máquinas **sozinho** e **atualiza a cada 5 minutos**, com bolinha de
🟢 online / ⚪ offline. Você **não digita IP** e **não digita usuário** — o ATLAS
detecta o usuário do Windows deste PC, e cada máquina aparece pelo **nome**
(ex.: `pc-praia`).

Por máquina: **testar**, **rodar comando** (e ver a saída), **área remota (RDP)**,
e — se o login recusar — um campo **usuário** para corrigir numa linha.

## O único passo do seu lado: instalar o Tailscale (grátis, ~2 min por PC)

É a peça que faz PCs em **casas diferentes** se enxergarem sem mexer em roteador.

1. Em **cada** computador, baixe em **tailscale.com/download** e instale.
2. **Entre com a MESMA conta** nos dois (Google/Microsoft serve).
3. Pronto. Abra o ATLAS como **admin → REDE**: as máquinas aparecem sozinhas.

Dica de ouro: na conta do Tailscale, ligue o **Tailscale SSH**. Aí você nem
precisa copiar chave — o login é resolvido pela sua conta do Tailscale.

> Se o Tailscale não estiver instalado, o painel te avisa e explica. Para PCs na
> **mesma casa** sem Tailscale, dá para **adicionar manual** (IP local) no fim do
> painel.

## Honestidade

Testei toda a lógica (descoberta, leitura da lista do Tailscale, usuário
automático, correção de usuário, recusa de máquina desconhecida, erros
graciosos). A conexão **ao vivo** depende do Tailscale + OpenSSH ligados nas suas
máquinas — comece pelo botão **testar**. Confiança alta na mecânica; o aperto de
mão real só dá para confirmar aí nos seus PCs.

## Como aplicar

Clique em **`fazer_update.bat`**. Cumulativo (confere por SHA-256, aplica só o
que falta, refaz os anteriores). `config/`, `.env` e `memory/` não são tocados.
