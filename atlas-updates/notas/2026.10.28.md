# Update ATLAS — 2026.10.28

Cumulativo. **Feche o ATLAS**, extraia, `fazer_update.bat`. Não toca em config/memória.

## 1) Telas de configuração não saem mais da tela
Os painéis **⚙ Recursos** e **⌁ 9Router** agora **rolam** (barra na lateral) e os
botões **SALVAR/CANCELAR ficam fixos embaixo**, sempre visíveis. A altura é
limitada à janela, então cabe em 1440x900 e telas menores. É só rolar para ver tudo.

## 2) API keys do Gemini no painel do 9Router
No mesmo painel onde ficam as chaves e configurações do 9Router (**Ctrl+9**),
agora há a seção **GEMINI (voz / Live)**:
- a **chave principal** do Gemini (a que ouve, vê e fala);
- **keys extras** (uma por linha) para rodízio, evitando travar por limite de uso.

(As mesmas opções continuam no painel Recursos; agora estão nos dois lugares.)

### Arquivos
Alterado: `ui.py`.
