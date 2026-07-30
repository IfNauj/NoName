import struct

def enviar_msg(conn, texto):
    dados = texto.encode("utf-8")
    conn.sendall(struct.pack(">I", len(dados)) + dados)

def receber_msg(conn, timeout=None, raw=False):
    if timeout: conn.settimeout(timeout)
    try:
        cab = conn.recv(4)
        if len(cab) != 4: return None
        tam = struct.unpack(">I", cab)[0]
        corpo = b""
        while len(corpo) < tam:
            pedaco = conn.recv(tam - len(corpo))
            if not pedaco: return None
            corpo += pedaco
        return corpo if raw else corpo.decode("utf-8", errors="replace")
    except:
        return None