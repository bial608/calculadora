# Update ATLAS — 2026.10.30 (autonomia)

Cumulativo. **Feche o ATLAS**, extraia, `fazer_update.bat`.

## O que você pediu: faz → olha → confirma → insiste até conseguir
1. **Confere o resultado de verdade.** Quando o ATLAS acha que terminou, ele
   **olha a tela de novo** e confirma se o que você pediu realmente aconteceu.
   Se não aconteceu, ele não diz "feito" — pega o que ainda falta e continua.
   (Antes ele às vezes dizia que terminou cedo demais.)
2. **Insiste de outro jeito.** Se um caminho falha ou ele trava repetindo a
   mesma coisa, ele **tenta outro caminho** em vez de desistir — até 5 tentativas
   diferentes / 10 minutos no modo Insistente.
3. **Quando realmente não dá**, ele te explica o que está faltando e oferece
   fazer junto, em vez de só dizer "não consegui".

## Controle (⚙ Recursos)
- **Persistência: Insistente** (novo padrão) ou **Normal**.
  - Insistente: confere + tenta outro caminho até conseguir (60 passos / 10 min).
  - Normal: tenta menos antes de te chamar (30 passos / 5 min).

Segurança: o **kill switch** (Ctrl+Shift+Alt+K), as **confirmações** (pagamento,
apagar muito, enviar a terceiros) e o **limite de tempo** continuam valendo —
ele insiste, mas dentro desses limites.

### Arquivos
Alterados: `actions/task_agent.py`, `ui.py`.
