"""Azure configurado por entorno; demo simulada y sin llamadas externas."""
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

class LimiteAzureError(RuntimeError):
    pass

class ClienteAves:
    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self._client = None

    def create(self, reintentar=True, **kwargs):
        if os.getenv("AVES_MODO_DEMO") == "1":
            return self._demo(kwargs.get("messages", []))
        names = ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_VERSION")
        if any(not os.getenv(name, "").strip() for name in names):
            raise RuntimeError("Configure las cuatro variables AZURE_OPENAI del entorno o use AVES_MODO_DEMO=1.")
        if self._client is None:
            self._client = OpenAI(api_key=os.environ["AZURE_OPENAI_API_KEY"], base_url=os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/") + "/openai/" + os.environ["AZURE_OPENAI_API_VERSION"] + "/", max_retries=0, timeout=20)
        kwargs["model"] = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        kwargs.setdefault("max_completion_tokens", 300)
        kwargs["extra_query"] = {"api-version": os.environ["AZURE_OPENAI_API_VERSION"]}
        for attempt in range(2 if reintentar else 1):
            try:
                return self._client.chat.completions.create(**kwargs)
            except RateLimitError:
                if reintentar and attempt == 0:
                    time.sleep(2)
                    continue
                raise LimiteAzureError("Azure alcanzo su limite de peticiones o tokens (429). Espere al menos un minuto antes de volver a intentar; el reintento corto no garantiza cuota disponible.") from None

    @staticmethod
    def _demo(messages):
        # Fixtures ilustrativas: no constituyen identificacion de especies.
        cases = [
            ("verde", "Quetzal", "Pharomachrus mocinno"),
            ("rojo", "Lapa roja", "Ara macao"),
            ("amarillo", "Pecho amarillo", "Pitangus sulphuratus"),
            ("azul", "Tangara azuleja", "Thraupis episcopus"),
            ("negro", "Zopilote negro", "Coragyps atratus"),
        ]
        text = " ".join(str(m.get("content", "")) for m in messages).lower()
        color, name, scientific = next((c for c in cases if c[0] in text or c[1].lower() in text or c[2].lower() in text), cases[0])
        record = {"nombre": name, "nombre_cientifico": scientific, "familia": "SIMULADO", "reino": "Animalia", "filo": "Chordata", "color": color, "peso": "SIMULADO", "alimento": "SIMULADO", "habitat": "SIMULADO", "descripcion": "Caso fijo de demostracion; no es una identificacion visual.", "simulado": True}
        if "lista json" in text:
            data = [record]
        elif "filtros" in text:
            data = {"simulado": True, "sugerencias": [record]}
        else:
            data = record
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(data, ensure_ascii=False)))])

cliente_aves = ClienteAves()
