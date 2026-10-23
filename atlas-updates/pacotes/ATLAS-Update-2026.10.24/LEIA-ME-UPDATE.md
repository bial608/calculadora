# Update ATLAS — 2026.10.24

Cumulativo: mostra a versão instalada e aplica só o que falta. **Feche o ATLAS**,
extraia e dê dois cliques em **`fazer_update.bat`**. API keys, `.env`, memória e
`.venv` não são tocados; `desfazer_update.bat` reverte.

## Foco deste update: segurança, controle e não ficar lento

### Kill switch (freio de emergência)
- **Ctrl+Shift+Alt+K** (ou `/kill` no console): para o agente na hora e bloqueia
  qualquer ação que mexa no sistema até você liberar (aperta de novo). A barra de
  status mostra `⛔KILL`.

### Guard (trava de verdade, não depende do modelo)
- Limite de ações que mexem no PC por hora.
- Confirmação obrigatória em: pagamento/compra, apagar muitos arquivos, enviar algo
  a terceiros. Tudo configurável no painel.

### Modo privado
- Um botão desliga os prints **e** a visão da tela/câmera de uma vez.

### Auditoria
- Tudo que o ATLAS faz vai para `memory/audit/<data>.jsonl` e para
  `ATLAS/Auditoria/<data>.md` (linha do tempo legível). `/audit` mostra as últimas.

### Custo e latência
- A barra de status mostra o gasto estimado do dia. Defina um orçamento diário no
  painel e ele avisa aos 80%. `/custo` detalha sessão/dia/latência.

### Saúde dos componentes
- `/health`: estado de cada parte; uma que quebra não derruba o resto.

### Otimização (não ficar lento com muitos recursos)
- Regra do projeto: o custo é o import pesado, não a feature existir. Cada recurso
  só carrega suas bibliotecas pesadas quando é usado de fato; recursos desligados
  nem viram ferramenta. Um teste automático impede regressão disso.

Tudo no painel **⚙ → RECURSOS** e nos comandos do Dev Console (F12):
`/kill` `/health` `/audit` `/custo`.

### Arquivos
Novos: `core/guard.py`, `core/audit.py`, `core/health.py`, `core/capabilities.py`.
Alterados: `main.py`, `ui.py`, `core/ninerouter.py`, `plugins/obsidian_brain.py`,
`core/hotkey.py`, docs.
