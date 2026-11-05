"""Registro de los modelos de tabla: importarlo registra las seis tablas en
SQLModel.metadata (create_all / drop_all) y permite resolver las relaciones entre módulos."""
from app.modules.duenios.models import Duenio, FichaDuenio
from app.modules.mascotas.models import Mascota
from app.modules.practicas.models import Practica
from app.modules.turnos.models import Turno, TurnoPractica

__all__ = ["Duenio", "FichaDuenio", "Mascota", "Practica", "Turno", "TurnoPractica"]
