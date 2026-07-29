from cryptography.fernet import Fernet

# MESMA CHAVE EXATA DO SEU CÓDIGO ORIGINAL
CHAVE = b'RAlFuqD9uFroOFgpJUPE5zWG0WjGEfewa4_MTUe_2MM='
CIFRA = Fernet(CHAVE)
TAM_CABECALHO = 4

def enviar_msg(sock, texto):
    dados = CIFRA.encrypt(str(texto).encode("utf-8"))
    cabecalho = len(dados).to_bytes(TAM_CABECALHO, byteorder="big")
    sock.sendall(cabecalho + dados)

def receber_msg(sock, timeout=None):
    try:
        if timeout: sock.settimeout(timeout)
        cabecalho = b""
        while len(cabecalho) < TAM_CABECALHO:
            parte = sock.recv(TAM_CABECALHO - len(cabecalho))
            if not parte: return None
            cabecalho += parte
        tam = int.from_bytes(cabecalho, byteorder="big")
        dados = b""
        while len(dados) < tam:
            parte = sock.recv(min(4096, tam - len(dados)))
            if not parte: return None
            dados += parte
        return CIFRA.decrypt(dados).decode("utf-8", errors="replace")
    except Exception:
        return None
    finally:
        if timeout: sock.settimeout(None)

def enviar_binario(sock, dados_bytes):
    cript = CIFRA.encrypt(dados_bytes)
    cabecalho = len(cript).to_bytes(TAM_CABECALHO, byteorder="big")
    sock.sendall(cabecalho + cript)

def receber_binario(sock, timeout=None):
    try:
        if timeout: sock.settimeout(timeout)
        cabecalho = b""
        while len(cabecalho) < TAM_CABECALHO:
            parte = sock.recv(TAM_CABECALHO - len(cabecalho))
            if not parte: return None
            cabecalho += parte
        tam = int.from_bytes(cabecalho, byteorder="big")
        dados = b""
        while len(dados) < tam:
            parte = sock.recv(min(8192, tam - len(dados)))
            if not parte: return None
            dados += parte
        return CIFRA.decrypt(dados)
    except Exception:
        return None
    finally:
        if timeout: sock.settimeout(None)