# ATLAS // A.T.L.A.S. · MARK LVI + 9Router

O **Gemini** é os ouvidos, os olhos e a voz. O **9Router** é o cérebro.

```
 você fala ─▶ Gemini Live (ouve + transcreve + vê tela/câmera)
                 │  refino bruto: limpa gagueira/ruído, mantém o sentido
                 ▼
            ask_9router(request, attach=screen|camera|both|file)
                 │  texto + transcrição crua + imagens / frames de vídeo / texto de PDF/DOCX
                 ▼
            9Router  http://localhost:20128/v1/chat/completions  (o modelo que você escolher)
                 │
                 ▼
            Gemini fala a resposta do 9Router, sem inventar nada por cima
```

### Só texto (padrão)

Nada além de texto chega ao 9Router — serve para modelos que não aceitam imagem/áudio.
Antes de enviar, o Gemini **decodifica** a mídia em texto explícito:

- todo texto visível transcrito literalmente (menus, abas, botões, URLs, números);
- **código, terminal, logs, stack traces, JSON, SQL**: copiados *exatamente*, em blocos
  ```` ```linguagem ```` com indentação preservada — sem corrigir nem resumir;
- mensagens de erro citadas palavra por palavra, com o app onde aparecem;
- tabelas/gráficos viram tabela markdown; vídeo vira sequência de frames com tempo;
  áudio vira transcrição com tempo;
- só fatos, sem responder a pergunta (quem responde é o 9Router); leitura duvidosa vem marcada com `[?]`.

O 9Router recebe: `[REQUEST]` + `[RAW TRANSCRIPT]` + `[MEDIA DECODED TO TEXT]`.
Você vê a decodificação no Dev Console (linhas `⇄`). Se a decodificação falhar, o pedido vai
assim mesmo, em texto, avisando o que não pôde ser lido — nunca vai imagem escondida.

Para modelos com visão dá pra trocar para **multimodal** no painel (Ctrl+9) ou com
`/textonly off` no console. Áudio é sempre decodificado (o protocolo não tem entrada de áudio).

Ações do computador (abrir app, volume, lembretes, memória, etc.) continuam nas
ferramentas que já existiam. Toda pergunta/conversa/análise vai pro 9Router.

---

## Ligar (Windows)

1. Instale o **Python 3.12** (python.org, marque *Add to PATH*).
2. Instale o **Node.js** e deixe o 9Router rodando:
   ```
   npx 9router
   ```
   Abra o dashboard em `http://localhost:20128`, conecte seus providers e crie uma **API Key**.
3. Dê dois cliques em **`INICIAR_ATLAS.bat`**.
   - Na primeira vez ele cria o `.venv`, instala tudo do `requirements.txt` e
     abre o assistente de configuração (chave do Gemini, endereço, chave e modelo do 9Router).
   - Nas próximas vezes ele só liga.

Reconfigurar a qualquer momento: **`CONFIGURAR_9ROUTER.bat`**, `INICIAR_ATLAS.bat --config`,
ou dentro do app com **Ctrl+9**.

macOS / Linux: `./iniciar_atlas.sh`

## Combos do 9Router

Os combos (cadeias de fallback criadas no dashboard) são detectados sozinhos e aparecem
**no topo da lista**, marcados com ◈, antes dos modelos avulsos. Ao escolher um, o painel
mostra a cadeia: `◈ combo 'premium-coding': cc/claude-sonnet-4-5 → gh/gpt-5 → if/kimi-k2`.

Três fontes, somadas:

| fonte | o quê |
|---|---|
| `GET /v1/models` com a API key | combos vêm com `owned_by: "combo"` |
| `GET /api/combos` (API do dashboard) | nome + cadeia de modelos |
| `~/.9router/db.json` (ou `DATA_DIR/db.json`) | combos salvos neste computador, mesmo sem a API responder |

Se o campo API KEY estiver vazio e o 9Router rodar neste PC, a primeira key ativa do
`db.json` é preenchida automaticamente. Combos de busca web (`webSearch`/`webFetch`) ficam de
fora, porque não são modelos de chat. A detecção roda ao abrir o painel (Ctrl+9), no botão
**⟳ DETECTAR**, no `configurar.py` e com `/combos` ou `/models` no console. A barra de status
marca o combo ativo com ◈.

## Identidade: ATLAS

- O prompt do Gemini diz "Your name is ATLAS".
- O prompt do 9Router manda responder como ATLAS e nunca se chamar Claude, GPT, Gemini, Kimi etc.,
  nem citar 9Router/combos/providers sem você perguntar.
- A regra de relay permite ao Gemini uma única alteração na resposta: trocar qualquer
  auto-identificação de outro modelo por ATLAS.
- Instalações antigas com `"assistant_name": "JARVIS"` são migradas para ATLAS ao ligar.

## Onde ficam as configurações

`config/api_keys.json` → bloco `"ninerouter"` (veja `config/api_keys.example.json`).
Se preferir não gravar a chave em disco, copie `.env.example` para `.env` —
variáveis de ambiente/`.env` têm prioridade:

| variável | exemplo |
|---|---|
| `NINEROUTER_ENABLED` | `1` |
| `NINEROUTER_BASE_URL` | `http://localhost:20128/v1` |
| `NINEROUTER_API_KEY` | `sk-...` |
| `NINEROUTER_MODEL` | `cc/claude-sonnet-4-5` |

`localhost` é trocado por `127.0.0.1` automaticamente (no Windows o `localhost`
resolve primeiro para IPv6 e o servidor pode recusar).

## O que foi adicionado na interface (nada foi removido)

| Onde | O quê |
|---|---|
| Barra abaixo do cabeçalho | prompt de shell ao vivo: `λ atlas@mark-lvi:~/core$ ears=gemini → brain=9router(modelo) ● ONLINE` + latência, nº de requisições, erros, tokens, uptime, versão do Python e PID |
| Rodapé da coluna central | **Dev Console** (F12): estilo terminal, mostra cada `POST /chat/completions`, a resposta, o tempo, os tokens, cada ferramenta chamada e o log da conversa |
| Linha de comando do console | `/help` `/test` `/combos` `/models` `/model <id>` `/on` `/off` `/textonly on\|off` `/ask <texto>` `/config` `/history clear` `/clear` — texto sem `/` vai pro assistente |
| ⚙ Setup | botão **⌁ 9ROUTER BRAIN** (Ctrl+9): liga/desliga a ponte, endereço, API key, combo/modelo (com DETECTAR), temperatura, timeout, max tokens, instruções extras, TESTAR |
| 🎛 Controls | botão **▣ DEV CONSOLE** |

## Arquivos novos / alterados

| arquivo | |
|---|---|
| `core/ninerouter.py` | cliente do 9Router (config, refino, histórico, envio de imagens, teste, listagem de modelos, eventos pro console) |
| `actions/ninerouter_relay.py` | ferramenta `ask_9router` que o Gemini chama; captura tela/câmera, lê imagem/vídeo (frames)/PDF/DOCX/PPTX/texto |
| `main.py` | instrução de relay no prompt do Gemini, envio da transcrição crua, eventos de ferramenta pro console |
| `ui.py` | `DevStatusBar`, `DevConsole`, `NineRouterOverlay`, atalhos F12 / Ctrl+9 |
| `INICIAR_ATLAS.bat`, `CONFIGURAR_9ROUTER.bat`, `iniciar_atlas.sh`, `configurar.py` | ligar e configurar |
| `.env.example`, `config/api_keys.example.json` | modelos de configuração |

## Problemas comuns

- **● OFFLINE na barra** → o 9Router não está rodando (`npx 9router`) ou o endereço está errado.
- **"recusou a API key"** → copie de novo a chave em Dashboard → API Keys.
- **"não existe aí"** → use ⟳ DETECTAR / `/combos` e escolha um combo ou modelo da lista.
- **Imagens não são entendidas** → o modelo escolhido no 9Router precisa aceitar visão.
- **Gemini às vezes responde sozinho** → é um modelo de voz seguindo instrução; a regra está
  reforçada no fim do prompt. Se acontecer, diga "pergunta pro cérebro" ou use `/ask` no console.

## Nome: ATLAS

Tudo que era JARVIS / J.A.R.V.I.S. / Jarvis / jarvis virou ATLAS / A.T.L.A.S. / Atlas / atlas
em todos os arquivos (classes `AtlasLive`, `AtlasUI`, pastas `~/.atlas_profiles`, `com.atlas.*`,
`atlas.ico`, `INICIAR_ATLAS.bat`, etc.).

**Única exceção, de propósito:** a palavra de ativação continua **"Hey Jarvis"**. Ela usa o modelo
pré-treinado `hey_jarvis` do openwakeword; não existe modelo pronto de "Hey Atlas", e renomear
quebraria a detecção. Se quiser "Hey Atlas", é preciso treinar um modelo próprio no openwakeword
e trocar `WAKE_MODEL` em `core/wake_word.py`.

## Plugin Obsidian Brain (memória + prints)

`plugins/obsidian_brain.py` — ligado por padrão. Detecta sozinho o vault que está aberto
no Obsidian (ou use ⚙ → PLUGIN SETTINGS → *Obsidian Brain* → caminho do vault → TESTAR VAULT).

```
<vault>/ATLAS/
  Conversas/2026-10-20 19-30 Conversa.md   transcrição ao vivo + Resumo, Problemas e soluções
                                            (tabela problema → como foi resolvido → status),
                                            Decisões, Pendências, [[Tópicos]]
  Conhecimento/<Assunto>.md                 nota criada quando o assunto ainda não existia;
                                            conversas seguintes sobre ele são acrescentadas
  Atividade/2026-10-20.md                   por print: 🟢 aprendi · 🔵 o que eu fiz · 🔴 sobre você
  Prints/                                   print temporário — apagado depois de estudado
  Perfil.md                                 quem você é, rotina, ferramentas, projetos,
                                            preferências e como o ATLAS pode ajudar melhor
```

**Antes de cada pergunta**, o vault inteiro é buscado só por **títulos, cabeçalhos, tags e
aliases**, num índice em memória atualizado pela data dos arquivos, sem varrer o texto.
Medido: 2.000 notas em cerca de 60 ms. Só as **seções** que batem vão para o 9Router, junto com o
resumo do seu Perfil. O Gemini usa a mesma busca pela ferramenta `obsidian_brain`, então os
dois veem a mesma memória. Se nada bater, a resposta vira uma nota nova.

**Resumo da conversa**: feito pelo 9Router (ou pelo Gemini, se a ponte estiver desligada) ao
fechar o ATLAS. Se o app cair, a transcrição já está salva e o resumo é feito ao ligar de novo.

**Prints**: a cada 3 min o ATLAS tira um print, o Gemini estuda **aquele print** e o ATLAS
escreve em `ATLAS/Atividade/<data>.md`, em callouts coloridos nativos do Obsidian:

```
## 14:03 · VS Code
*Você estava:* editando main.py do ATLAS

> [!success] 🟢 Aprendi          ← verde: o que ele aprendeu com o print
> - Projeto ATLAS em Python com PyQt6

> [!info] 🔵 O que eu fiz         ← azul: o que o ATLAS fez desde o print anterior
> - Tarefa — enviei a mensagem para a Maria

> [!danger] 🔴 Sobre você         ← vermelho: o que ele percebeu sobre você
> - Prefere atalhos de teclado
```

**Depois de salvar, o print é apagado.** Se a análise falhar (sem internet, cota), o print fica
guardado e é estudado de novo no próximo ciclo ou ao religar; os não analisados somem após
14 dias. O Dev Console (F12) mostra as mesmas linhas nas mesmas cores. Telas iguais não geram
print novo. Os prints **pausam sozinhos** se o título da janela ativa tiver *senha, password,
banco, bank, pix, cartão, 1password, bitwarden, keepass, anônima…* (lista editável).
Por voz: "pausa os prints" / "volta os prints".
⚠ Os prints ficam dentro do vault: se ele sincroniza (Obsidian Sync, iCloud, Drive), os prints
vão junto.

Suas próprias notas **nunca são editadas**, só lidas e linkadas. O ATLAS só altera notas que
ele mesmo criou (`source: atlas` no frontmatter).

Como escrever outros plugins: veja `PLUGINS-COMO-FAZER.md`.

## Autonomia: tarefas completas de uma vez

Peça a tarefa inteira, por exemplo *"manda no WhatsApp pra Maria que eu vou me atrasar 10 minutos"*.
O ATLAS chama a ferramenta **`executar_tarefa`**, que funciona assim:

1. **Planeja**: o 9Router quebra o pedido em etapas (só texto, combina com os seus modelos).
2. **Olha, age e confere**: tira um print da tela, o Gemini escolhe UMA ação (abrir app, clicar,
   digitar, atalho, rolar), o ATLAS executa, espera a tela parar de mudar e olha de novo.
3. **Se travar**: a mesma ação na mesma tela faz o 9Router replanejar (até 2 vezes).
4. **Termina** só quando o resultado aparece na tela (ex.: a mensagem enviada no chat) e te fala
   o que aconteceu.

Enquanto trabalha, a janela do ATLAS é minimizada e volta no fim. Cada passo aparece no
Dev Console (linhas `⚙ agent`).

**Parar:** ESC, dizer "para a tarefa", `/stop` no console, ou jogar o mouse num canto da tela
(parada de emergência).
**Ele para e te pergunta** antes de: digitar senha ou código, pagar ou comprar, apagar coisas,
aceitar termos, ou quando há dois contatos com o mesmo nome.
Limites: 30 passos ou 5 minutos por tarefa.

O `send_message` (WhatsApp, Telegram…) também usa o agente quando não há driver próprio do app,
em vez de digitar às cegas.

No console: `/tarefa <objetivo>` executa direto, sem voz.

## Painel Recursos (⚙ → RECURSOS)

Um lugar para ligar/desligar cada recurso, com pequenas configurações:

- **🎙 Palavra de ativação** — responder só quando chamado. Duas opções:
  *Hey Jarvis* (pronto, openwakeword) ou *Ei ATLAS* (personalizada, via
  **Porcupine/Picovoice**: `pip install pvporcupine`, uma *access key* grátis em
  console.picovoice.ai e o arquivo `.ppn` da frase que você cria lá). Se o
  Porcupine não estiver pronto, cai sozinho no *Hey Jarvis*.
- **✋ Interromper falando (barge-in)** — pode cortar o ATLAS falando por cima;
  a conversa continua de onde parou com a informação nova. Desligável.
- **⚡ Modo rápido** — nas tarefas, faz uma sequência curta de passos por olhada
  (só o 1º mexe o mouse; o resto é teclado), ficando mais ágil.
- **🔔 Avisos em background** — chave geral + sub-opções: hardware (HD cheio,
  CPU, temperatura), assuntos acompanhados, lembretes por horário/contexto.
- **👁 Visão** — deixar o ATLAS ver a tela e a webcam (quando desligado, ele
  nem recebe as ferramentas de visão e sabe que não pode ver).

Mudanças em visão, barge-in e palavra de ativação valem ao salvar (ele reconecta).
