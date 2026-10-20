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
| Linha de comando do console | `/help` `/test` `/models` `/model <id>` `/on` `/off` `/textonly on\|off` `/ask <texto>` `/config` `/history clear` `/clear` — texto sem `/` vai pro assistente |
| ⚙ Setup | botão **⌁ 9ROUTER BRAIN** (Ctrl+9): liga/desliga a ponte, endereço, API key, modelo (com LISTAR), temperatura, timeout, max tokens, instruções extras, TESTAR |
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
- **"modelo não existe"** → use LISTAR / `/models` e escolha um id exato (ou um *combo* criado no 9Router).
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
