# ATLAS — Update 2026.11.01 · Rede (controlar seus outros PCs)

## O que chega

Agora, entrando como **admin**, aparece o painel **🖧 REDE** — para controlar os
seus **outros computadores** a partir do principal.

**Como funciona (e por que é seguro):** o ATLAS não abre servidor nenhum nem
inventa senha. Ele usa o **OpenSSH**, que o Windows 10/11 já trazem embutido.
Cada comando e cada arquivo passam por `ssh`/`scp` — autenticados por **chave
SSH**, criptografados. Não fica backdoor no ATLAS: desligar o SSH numa máquina
corta todo o acesso.

No painel você pode, para cada máquina:
- **testar** a conexão;
- **rodar comando** e ver a saída (ex.: `shutdown /r /t 0`, abrir um programa…);
- **área remota** — abre a Área de Trabalho Remota (RDP) daquela máquina;
- **copiar chave** — a linha exata para autorizar este PC na outra máquina;
- **apagar** a máquina da lista.

Também dá para mandar por **voz**: "ATLAS, no PC da sala, rode tal coisa" — ele
só aceita máquinas que você cadastrou (nome errado falha com segurança, nunca
toca numa máquina desconhecida). O kill switch corta os comandos remotos também.

## Preparar cada PC que você quer controlar (uma vez)

1. **Configurações → Apps → Recursos opcionais → Adicionar → "OpenSSH Server"**.
2. No **PowerShell como administrador**:
   ```
   Start-Service sshd
   Set-Service  sshd -StartupType Automatic
   ```
3. **Login por chave** (o painel não tem onde digitar senha). No PC principal:
   ```
   ssh-keygen -t ed25519
   ```
   depois use o botão **copiar chave** no painel e cole a linha no PowerShell —
   ela autoriza este PC na outra máquina (pede a senha dela uma vez).
4. Para a **área remota**: na outra máquina, **Configurações → Sistema → Área de
   Trabalho Remota → Ativar**.

> Honestidade: testei toda a lógica (montagem dos comandos, cadastro, recusa de
> máquina desconhecida, erros graciosos). A conexão SSH ao vivo só dá para
> confirmar nas suas máquinas, depois do passo acima — comece pelo botão
> **testar**.

## Como aplicar

Clique em **`fazer_update.bat`**. Cumulativo: confere por SHA-256, aplica só o
que falta e refaz os updates anteriores. `config/`, `.env` e `memory/` não são
tocados.
