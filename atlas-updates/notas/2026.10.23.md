# Update ATLAS — 2026.10.23

Cumulativo: aplica tudo desde a versão original, tendo você usado os updates
anteriores ou não. Só copia o que ainda falta. **Feche o ATLAS**, extraia e dê
dois cliques em **`fazer_update.bat`** (o resto fica em `_sistema`). API keys,
`.env`, memória e `.venv` não são tocados; `desfazer_update.bat` reverte.

## Novo: painel RECURSOS (⚙ → RECURSOS)
Botões para ligar/desligar cada recurso, com pequenas configurações.

### Palavra de ativação "Ei ATLAS"
- Escolha entre **Hey Jarvis** (pronto) e **Ei ATLAS** (personalizada, Porcupine).
- Para "Ei ATLAS": `pip install pvporcupine`, pegue uma access key grátis em
  console.picovoice.ai e crie lá a frase (baixa um arquivo `.ppn`). Cole a key e
  o caminho do `.ppn` no painel. Sem isso, ele usa "Hey Jarvis" automaticamente.

### Interromper falando (barge-in) — agora funciona
Antes o microfone ficava fechado enquanto o ATLAS falava. Agora você pode cortar
falando por cima: ele separa a sua voz do eco dele mesmo e para para te ouvir, sem
perder o contexto. Dá pra desligar no painel.

### Modo rápido
Nas tarefas, ele executa uma sequência curta de passos por olhada em vez de um de
cada vez — mais rápido. (Só o primeiro passo mexe o mouse; os seguintes são de
teclado, para não errar depois que a tela muda.)

### Avisos em background com botão
A chave geral desliga todos os avisos não solicitados, e há sub-opções: hardware
(HD cheio, CPU, temperatura), assuntos acompanhados, e lembretes por horário/contexto.

### Visão com botão
Liga/desliga a visão da tela e da webcam.

## Já existia (verificado)
Controle do PC (abrir apps, volume, prints, pastas), visão por webcam, clima,
busca na web, lembretes, memória no Obsidian e leitura de PDFs/documentos já
estavam no projeto e seguem funcionando — agora com os botões acima.

## Ainda NÃO incluído (precisa de contas externas)
Google Calendar, Spotify e Gmail dependem de login/OAuth de cada serviço e são
melhor feitos como plugins dedicados — posso fazer isso num próximo update, testado.

### Arquivos
Novos: `core/wake_word.py` (Porcupine), `FeaturesOverlay` em `ui.py`.
Alterados: `main.py`, `ui.py`, `core/wake_word.py`, `actions/task_agent.py`,
`memory/config_manager.py`, docs.
