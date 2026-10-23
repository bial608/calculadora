# ATLAS — Update 2026.10.31 · Login e contas

## O que chega neste update

**Tela de login ao abrir o ATLAS.** Agora você entra com **nickname + senha**.
Pode **se registrar** (cria uma conta nova) ou **fazer login** numa que já existe.
A senha é guardada embaralhada (PBKDF2), nunca em texto puro.

**Conta admin embutida:** login `admin`, senha `bialrubi`.

**Cada conta tem os seus próprios dados.** Configurações, memória, habilidades e
auditoria de cada conta ficam separadas, em `profiles/<conta>/`. Uma conta não vê
os arquivos da outra.

**Painel ADMIN** (só aparece quando você entra como `admin`): lista todas as
contas **deste computador**, mostra o que cada uma salvou (config, tamanho da
memória, nº de habilidades, dias de auditoria) e deixa você:

- **entrar como** qualquer conta (reinicia o ATLAS naquela conta);
- **abrir a pasta** da conta para ver os arquivos de verdade;
- **apagar** uma conta (com confirmação; a conta `admin` e a que está em uso não
  podem ser apagadas).

> Isto é **local**: o admin enxerga as contas guardadas nesta máquina. Não é
> acesso à máquina de outra pessoa. A camada de rede (controlar vários
> computadores seus) é o próximo passo e será discutida à parte.

## Se você já usava o ATLAS

Nada é perdido. Na **primeira vez** que você fizer login, a configuração e a
memória que já existiam (sua chave do Gemini, 9Router, tudo) são **copiadas para
a sua conta** automaticamente. Suas API keys e ajustes continuam valendo.

## Como aplicar

Clique em **`fazer_update.bat`**. O updater é cumulativo: ele confere item por
item (SHA-256), aplica só o que falta e **verifica também todos os updates
anteriores**, preenchendo qualquer coisa que tenha ficado para trás. Nada do que
você configurou (`config/api_keys.json`, `.env`, `memory/`, certificados) é
tocado. Para voltar atrás, `desfazer_update.bat`.
