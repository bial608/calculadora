# Update ATLAS — 2026.10.25

Correção dos dois problemas do mouse. Cumulativo: **feche o ATLAS**, extraia e
dê dois cliques em **`fazer_update.bat`**. Não toca em API keys/memória/`.env`.

## 1) Clica no lugar errado (perto, mas não no alvo)
Causa: a tela com escala/alta-DPI. O ATLAS "enxergava" o print num tamanho e
movia o mouse em outro, então a conta do ponto saía torta (pior perto das bordas),
e o zoom de refinamento piorava. Agora toda a conta é feita em cima do print e
convertida para o mouse **uma vez só**, pela razão entre os dois tamanhos. No
Windows o ATLAS também fica "DPI-aware", então print, tamanho da tela e mouse
passam a usar os mesmos pixels. Isso conserta a mira em 1440x900 com 125%/150%
de escala.

## 2) Diz que clicou mas o mouse não vai
Antes ele só anunciava o clique, sem checar. Agora ele confere se o mouse chegou
ao ponto; se não chegou, avisa honestamente em vez de dizer que clicou. E no
começo de cada tarefa faz um teste rápido: se o sistema não deixa controlar o
mouse, ele te diz o motivo e como resolver, por sistema:
- **Linux (Wayland):** o Wayland não deixa controlar o mouse. Troque para uma
  sessão **X11/Xorg** na tela de login.
- **macOS:** libere em Preferências → Privacidade → **Acessibilidade** para o
  Python/ATLAS.
- **Windows:** se a janela-alvo for de administrador, rode o ATLAS como admin.

## Diagnóstico
No Dev Console (F12): **`/diag`** testa se o mouse funciona e mostra a escala da
tela (ex.: `print 2880x1800 ≠ mouse 1440x900 → corrigido`).

### Arquivos
Alterado: `actions/task_agent.py`.
