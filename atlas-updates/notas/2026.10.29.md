# Update ATLAS — 2026.10.29

Cumulativo. **Feche o ATLAS**, extraia, `fazer_update.bat`.

## 1) Intervalo dos prints em SEGUNDOS
Agora dá para configurar o tempo entre os prints em segundos (⚙ → PLUGIN
SETTINGS → Obsidian Brain → "Intervalo dos prints (segundos)"). Ex.: 60, 180,
300. Mínimo 15s. Configurações antigas em minutos continuam valendo.

## 2) Para ele ERRAR MENOS nos cliques
Resposta curta: o que decide onde clicar é a **visão do Gemini**, não o 9Router.
Então, para acertar mais:
- Use o perfil **Preciso** (⚙ Recursos → Velocidade): zoom de refino sempre
  ligado, imagem maior.
- E/ou escolha um **modelo de visão mais forte** na nova seção **🎯 PRECISÃO DOS
  CLIQUES**: o **gemini-2.5-pro** aponta bem melhor (mais lento e caro, mas
  acerta mais). Deixe em "Automático" para seguir o perfil de velocidade.

Trocar o cérebro/combo do 9Router **não** muda a precisão dos cliques.

### Arquivos
Alterados: `plugins/obsidian_brain.py`, `ui.py`, `actions/task_agent.py`.
