# Update ATLAS — 2026.10.27 (velocidade)

Cumulativo. **Feche o ATLAS**, extraia, `fazer_update.bat`. Não toca em config/memória.

## Primeiro, a verdade sobre velocidade
As tarefas são **passo a passo**: ele precisa ver o resultado de um passo para
decidir o próximo, então não dá para "pensar na próxima enquanto faz a atual"
dentro da mesma tarefa. O que deixa lento é a **chamada de visão a cada passo**
(e duas por clique: uma pra decidir, outra pro zoom). Então o que realmente
acelera é **reduzir essas chamadas** — foi o que fiz.

## Perfis de velocidade (⚙ RECURSOS → Velocidade, ou /speed)
- **Preciso** — como era antes.
- **Equilibrado** (novo padrão) — mais rápido mantendo boa precisão: o zoom de
  refino só acontece quando o alvo é grande/ambíguo, espera menos entre passos,
  faz vários passos de teclado de uma vez.
- **Turbo** — o mais rápido: modelo de visão mais leve, sem zoom na maioria dos
  cliques, espera mínima.

## O maior ganho: tarefas que ele já aprendeu
Quando o ATLAS já tem a habilidade salva, no Equilibrado/Turbo ele roda **quase
sem olhar a tela**: executa os passos de teclado direto e só usa a visão para os
cliques. Medido: uma tarefa de 6 passos passou de ~6-8 chamadas de visão para
**1**. Se a tela tiver mudado e ele não achar o alvo, volta sozinho para o modo
cuidadoso.

## Várias API keys do Gemini (você pediu)
No painel dá para colar **API keys extras do Gemini** (uma por linha). Ele faz
rodízio entre elas. Seja claro: isso **não deixa uma tarefa mais rápida** — serve
para **não travar** quando uma key bate no limite de uso (evita as esperas de
cota quando você usa bastante).

## Comandos (F12)
`/speed preciso|equilibrado|turbo` · o painel também tem o seletor.

### Arquivos
Alterados: `actions/task_agent.py`, `core/gemini.py`, `ui.py`.
