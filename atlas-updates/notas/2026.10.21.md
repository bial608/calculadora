# Update ATLAS — 2026.10.21

## Como instalar

1. **Feche o ATLAS.**
2. Extraia esta pasta em qualquer lugar. O mais fácil é dentro da pasta do ATLAS.
3. Dê dois cliques em **`fazer_update.bat`**.
   - Ele encontra a pasta do ATLAS sozinho. Se houver mais de uma, pergunta qual; se não
     achar, abre uma janela para você escolher.
   - Copia só os arquivos novos ou alterados.
   - **Não toca** em `config/api_keys.json` (Gemini, 9Router, plugins, nome), `.env`,
     memória, `.venv` e certificados.
   - Faz backup de tudo que substitui em `<ATLAS>/_update_backups/`.
4. Abra o ATLAS pelo `INICIAR_ATLAS.bat`, como sempre.

Deu algo errado? **`desfazer_update.bat`** volta exatamente ao que era antes.

## O que vem neste update

### Autonomia: tarefas completas de uma vez
- Nova ferramenta **`executar_tarefa`**. Peça a tarefa inteira, por exemplo *"manda no WhatsApp
  pra Maria que eu vou me atrasar"*, e o ATLAS:
  1. planeja as etapas com o 9Router (só texto);
  2. olha a tela, faz uma ação, confere, e repete até ver o resultado na tela;
  3. se travar, replaneja; no fim, te conta o que aconteceu.
- O prompt agora manda o ATLAS terminar o pedido inteiro sem te pedir para dividir em partes.
- `send_message` (WhatsApp, Telegram…) usa o agente em vez de digitar às cegas.
- Para parar: **ESC**, "para a tarefa", `/stop` no console ou mouse num canto da tela.
- Ele **para e pergunta** antes de senha, pagamento, compra, apagar coisas, aceitar termos,
  ou quando há dois contatos com o mesmo nome.

### Prints: aprende, salva colorido e apaga
- Cada print (a cada 3 min) é estudado na hora e vira uma entrada em
  `ATLAS/Atividade/<data>.md` com três blocos coloridos do Obsidian:
  🟢 **Aprendi** (verde) · 🔵 **O que eu fiz** (azul) · 🔴 **Sobre você** (vermelho).
- **Depois de salvar, o print é apagado.** Se a análise falhar, ele fica e é estudado de novo
  depois.
- O Dev Console (F12) mostra as mesmas linhas nas mesmas cores.

### Arquivos
Novos: `actions/task_agent.py`, `core/activity.py`.
Alterados: `main.py`, `ui.py`, `actions/send_message.py`, `plugins/obsidian_brain.py`, docs.
