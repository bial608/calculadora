# Update ATLAS — 2026.10.22

Pacote cumulativo: aplica tudo de uma vez, tendo você usado o update anterior ou não.
Só os arquivos que ainda não estão atualizados são copiados.

## Como instalar

1. **Feche o ATLAS.**
2. Extraia esta pasta em qualquer lugar.
3. Dê dois cliques em **`fazer_update.bat`** (o resto fica na subpasta `_sistema`, não precisa abrir).
   - Acha a pasta do ATLAS, confirma com você, copia só o que mudou.
   - **Não toca** em API keys, `.env`, memória, `.venv` nem certificados.
   - Guarda backup; **`desfazer_update.bat`** volta ao estado anterior.

## O que vem

### Cliques muito mais precisos
Antes o ATLAS clicava perto, mas não no ponto certo. A causa: o Gemini aponta
no formato [y, x] e o código pedia [x, y]. Agora:
- usa o formato nativo do Gemini (uma caixa ao redor do elemento);
- dá um **zoom** na região e olha de novo para acertar o centro;
- no Windows, encaixa o clique no botão/campo real sob o ponto.

### Ele aprende as tarefas (memória de habilidades)
- Quando uma tarefa dá certo, o ATLAS **salva os passos** numa nota em
  `ATLAS/Habilidades/<tarefa>.md` (ou `memory/habilidades/` se não houver vault).
- Da próxima vez que você pedir a mesma coisa, ele segue a receita — mais rápido
  e sem errar — mas ainda confere a tela a cada passo, então se o app mudou ele se adapta.
- A nota é editável: tem um bloco JSON que você pode corrigir no Obsidian.

### "Vamos fazer juntos" (por voz)
- Se ele não conseguir sozinho, oferece aprender com você.
- Você guia **um passo de cada vez por voz** ("abre o WhatsApp", "clica na busca",
  "escreve oi"); ele faz cada passo e, quando você diz "pronto", salva como habilidade.
- (Não há gravação de mouse/teclado — você conduz falando.)

### Mutar o microfone de qualquer lugar
- **Ctrl + Shift + Alt + Espaço** liga/desliga o microfone, mesmo com outra janela na frente
  (no Windows). Não conflita com o Ctrl+Espaço do push-to-talk.

### Prints agora com 5 cores no Obsidian
Em `ATLAS/Atividade/<data>.md`, por print:
- 🟢 **verde** — o que aprendi com o print
- 🔵 **azul** — o que eu fiz sozinho (ambiente)
- 🔴 **vermelho** — o que percebi sobre você
- 🟣 **roxo** — o que fiz **a seu pedido** e como
- 🟡 **amarelo** — o que aprendi pra ser **mais autônomo**

### Arquivos
Novos: `actions/task_agent.py`, `actions/teach_task.py`, `core/activity.py`, `core/skills.py`.
Alterados: `main.py`, `ui.py`, `core/hotkey.py`, `actions/send_message.py`,
`plugins/obsidian_brain.py`, docs.
