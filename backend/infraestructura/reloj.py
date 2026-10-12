"""La hora del sistema, en UTC. Implementa el puerto Reloj."""
from datetime import datetime, timezone

from dominio.puertos_usuarios import Reloj


class RelojSistema(Reloj):
    def ahora(self) -> datetime:
        return datetime.now(timezone.utc)
