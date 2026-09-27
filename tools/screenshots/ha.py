"""Hilfen: Onboarding, Token, REST und WebSocket gegen die Demo-Instanz."""
import asyncio, json, os, aiohttp
BASE = "http://127.0.0.1:8123"
CLIENT = BASE + "/"
TOKFILE = os.path.join(os.path.dirname(__file__), ".token.json")

async def onboard(s):
    r = await s.post(BASE + "/api/onboarding/users", json={
        "client_id": CLIENT, "name": "Anna", "username": "anna",
        "password": "demo-demo", "language": "de"})
    code = (await r.json())["auth_code"]
    r = await s.post(BASE + "/auth/token", data={
        "grant_type": "authorization_code", "code": code, "client_id": CLIENT})
    tok = await r.json()
    h = {"Authorization": "Bearer " + tok["access_token"]}
    await s.post(BASE + "/api/onboarding/core_config", headers=h)
    await s.post(BASE + "/api/onboarding/analytics", headers=h)
    await s.post(BASE + "/api/onboarding/integration", headers=h,
                 json={"client_id": CLIENT, "redirect_uri": CLIENT + "?auth_callback=1"})
    json.dump(tok, open(TOKFILE, "w"))
    return tok

async def token(s):
    tok = json.load(open(TOKFILE))
    r = await s.post(BASE + "/auth/token", data={
        "grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": CLIENT})
    return (await r.json())["access_token"]

class WS:
    def __init__(self, s, access): self.s, self.access, self.i = s, access, 0
    async def __aenter__(self):
        self.ws = await self.s.ws_connect(BASE + "/api/websocket")
        await self.ws.receive_json()
        await self.ws.send_json({"type": "auth", "access_token": self.access})
        assert (await self.ws.receive_json())["type"] == "auth_ok"
        return self
    async def __aexit__(self, *a): await self.ws.close()
    async def call(self, **msg):
        self.i += 1
        await self.ws.send_json({"id": self.i, **msg})
        while True:
            m = await self.ws.receive_json()
            if m.get("id") == self.i and m.get("type") == "result":
                if not m["success"]: raise RuntimeError(m)
                return m.get("result")
