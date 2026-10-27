"""Cuentas y sesiones en SQLite."""
import sqlite3
from dataclasses import replace
from datetime import datetime

from dominio.errores_usuarios import CorreoYaRegistrado
from dominio.puertos_usuarios import ConsultaCuentas, ListadoCuentas, RegistroCuentas, SesionesAbiertas
from dominio.usuarios import Correo, ResumenUsuario, Rol, Sesion, Usuario
from infraestructura.sqlite.base_datos import BaseDatos, cabe_en_sqlite


class RepositorioUsuariosSqlite(ConsultaCuentas, RegistroCuentas, ListadoCuentas):
    def __init__(self, bd: BaseDatos):
        self._bd = bd

    def por_correo(self, correo: Correo) -> Usuario | None:
        return self._uno("SELECT * FROM usuario WHERE correo = ?", (correo.valor,))

    def por_id(self, usuario_id: int) -> Usuario | None:
        if not cabe_en_sqlite(usuario_id):
            return None
        return self._uno("SELECT * FROM usuario WHERE id = ?", (usuario_id,))

    def guardar(self, usuario: Usuario) -> Usuario:
        datos = (usuario.correo.valor, usuario.nombre, usuario.hash_contrasena, usuario.rol.value, int(usuario.activo))
        try:
            with self._bd.conexion() as conexion:
                if usuario.id is None:
                    cursor = conexion.execute(
                        "INSERT INTO usuario (correo, nombre, hash_contrasena, rol, activo) VALUES (?, ?, ?, ?, ?)",
                        datos,
                    )
                    return replace(usuario, id=cursor.lastrowid)
                conexion.execute(
                    "UPDATE usuario SET correo = ?, nombre = ?, hash_contrasena = ?, rol = ?, activo = ? WHERE id = ?",
                    (*datos, usuario.id),
                )
                return usuario
        except sqlite3.IntegrityError as error:
            if "UNIQUE" in str(error):
                raise CorreoYaRegistrado(usuario.correo.valor) from None
            raise

    def resumenes(self) -> list[ResumenUsuario]:
        with self._bd.conexion() as conexion:
            filas = conexion.execute(
                "SELECT u.id, u.correo, u.nombre, u.rol, u.activo, COUNT(p.id) AS cantidad_plantas "
                "FROM usuario u LEFT JOIN planta p ON p.usuario_id = u.id "
                "GROUP BY u.id ORDER BY u.id"
            ).fetchall()
        return [
            ResumenUsuario(f["id"], f["correo"], f["nombre"], Rol(f["rol"]), bool(f["activo"]), f["cantidad_plantas"])
            for f in filas
        ]

    def eliminar(self, usuario_id: int) -> None:
        # Las llaves foraneas borran en cascada sus sesiones, plantas, sensores e historial.
        with self._bd.conexion() as conexion:
            conexion.execute("DELETE FROM usuario WHERE id = ?", (usuario_id,))

    def _uno(self, consulta: str, parametros: tuple) -> Usuario | None:
        with self._bd.conexion() as conexion:
            fila = conexion.execute(consulta, parametros).fetchone()
        if fila is None:
            return None
        return Usuario(
            fila["id"], Correo(fila["correo"]), fila["nombre"], fila["hash_contrasena"], Rol(fila["rol"]), bool(fila["activo"])
        )


class RepositorioSesionesSqlite(SesionesAbiertas):
    def __init__(self, bd: BaseDatos):
        self._bd = bd

    def abrir(self, sesion: Sesion) -> None:
        with self._bd.conexion() as conexion:
            conexion.execute(
                "INSERT INTO sesion (token_id, usuario_id, vence_en) VALUES (?, ?, ?)",
                (sesion.token_id, sesion.usuario_id, sesion.vence_en.isoformat()),
            )

    def abierta(self, token_id: str) -> Sesion | None:
        with self._bd.conexion() as conexion:
            fila = conexion.execute(
                "SELECT token_id, usuario_id, vence_en FROM sesion WHERE token_id = ?", (token_id,)
            ).fetchone()
        if fila is None:
            return None
        return Sesion(fila["token_id"], fila["usuario_id"], datetime.fromisoformat(fila["vence_en"]))

    def cerrar(self, token_id: str) -> None:
        with self._bd.conexion() as conexion:
            conexion.execute("DELETE FROM sesion WHERE token_id = ?", (token_id,))

    def cerrar_de_usuario(self, usuario_id: int) -> None:
        with self._bd.conexion() as conexion:
            conexion.execute("DELETE FROM sesion WHERE usuario_id = ?", (usuario_id,))
