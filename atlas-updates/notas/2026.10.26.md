# Update ATLAS — 2026.10.26 (Windows: mouse de novo)

Cumulativo. **Feche o ATLAS**, extraia, `fazer_update.bat`. Não toca em config/memória.

## O que estava errado (e agora corrigido)
1. **O DPI era ligado tarde demais.** No update anterior eu ligava o modo DPI
   depois que a interface já tinha iniciado, então não pegava — por isso ele
   "via" a tela menor (tipo 1280x720) e o mouse ia pro lugar errado. Agora o DPI
   é ligado **antes de tudo**, então print, tamanho da tela e mouse passam a usar
   os mesmos pixels. Isso faz o **mover** acertar.
2. **Eu estava cancelando o clique.** A verificação que eu tinha colocado achava
   que o mouse "não tinha chegado" (por causa do DPI) e **cancelava o clique** —
   era isso que fazia "tentei clicar, verifica se foi". Agora o clique **sempre
   acontece**; a verificação só adiciona um aviso, nunca cancela.
3. **Clique mais firme.** Alguns programas ignoram o clique sintético muito
   rápido. Agora é um aperta-segura-solta de verdade.

## Se ainda não clicar, só duas causas no Windows
- **Janela de administrador:** se o programa-alvo foi aberto como administrador,
  o Windows ignora cliques de um programa normal. **Abra o ATLAS como
  administrador** (clique direito no INICIAR_ATLAS.bat → Executar como
  administrador). O `/diag` avisa quando esse é o caso.
- **Resolução detectada errada:** rode **`/diag`** no console (F12). Se os
  números não baterem com a sua tela, force com **`/setres 1440x900`**. Volta ao
  automático com `/setres auto`.

## Como testar
1. Atualize e abra o ATLAS **como administrador**.
2. F12 → `/diag` → me mande a linha que aparecer.
3. Peça um clique e veja se foi.

### Arquivos
Alterados: `main.py`, `actions/task_agent.py`, `ui.py`.
