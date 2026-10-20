# Como os plugins do ATLAS são feitos

Um plugin é **um arquivo `.py` em `plugins/`**. O ATLAS descobre sozinho ao ligar
(`core/plugin_loader.py`). Arquivos que começam com `_` são ignorados, e servem como helpers.
Modelo pronto: `plugins/_template.py`.

## O mínimo

```python
PLUGIN = {
    "name": "meu_plugin",                 # único, snake_case
    "description": "Quando o Gemini deve chamar isso (seja explícito).",
    "parameters": {"type": "OBJECT",
                   "properties": {"texto": {"type": "STRING", "description": "..."}},
                   "required": []},
}

def run(parameters: dict, player=None) -> str:
    return "Texto que o ATLAS vai falar."     # nunca deixe exceção escapar
```

- `PLUGIN` vira uma **ferramenta** que o Gemini pode chamar; `run()` executa.
- `player` é a interface (`player.write_log(...)`, `player.show_content(titulo, texto)`).
- Para perguntar algo a um modelo, use `core.gemini` (`gemini.text`, `gemini.as_json`,
  `gemini.call`). Ele já tem timeout, troca de modelo e provedores. Para o cérebro do
  9Router, use `core.ninerouter.complete(prompt)`.

## Opcionais

| o quê | para quê |
|---|---|
| `PLUGIN_SETTINGS = {"namespace", "title", "fields": [...], "action": {...}}` | formulário em ⚙ → PLUGIN SETTINGS (campos `text`, `password`, `toggle`, `choice` + botão de teste). Ler com `memory.config_manager.get_plugin_config(ns)` |
| `"behavior": "NON_BLOCKING"`, `"scheduling": "WHEN_IDLE"` em `PLUGIN` | ferramenta demorada que não trava a fala |
| `"tier": "core"`, `"brief": "..."` | prioridade quando um modelo pequeno recebe poucas ferramentas |
| `on_load(ctx)` | roda uma vez ao ligar (`ctx`: player, speak, base_dir, log), para iniciar threads e registrar ganchos |
| `on_turn(usuario, resposta)` | depois de cada troca da conversa (em thread separada) |
| `on_shutdown()` | ao fechar o ATLAS (prazo de 45 s) |
| `ninerouter.add_context_provider(fn)` | `fn(pedido) -> texto` anexado a **toda** pergunta enviada ao 9Router |
| `ninerouter.add_answer_hook(fn)` | `fn(pedido, resposta)` depois de cada resposta do 9Router |
| `ninerouter.emit("info", text=...)` | escrever no Dev Console (F12) |

Os quatro últimos (`on_load`, `on_turn`, `on_shutdown` e os ganchos do 9Router) foram
adicionados para o Obsidian Brain, mas servem para qualquer plugin.
Liga/desliga por plugin: ⚙ → PLUGINS.

Exemplo completo e real: `plugins/obsidian_brain.py`.
