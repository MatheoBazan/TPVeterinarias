import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integracion

ANA = {
    "id": 1,
    "nombre": "Ana Gómez",
    "email": "ana.gomez@example.com",
    "ficha": {"id": 1, "duenio_id": 1, "telefono": "11 5555-0101", "direccion": "Calle Falsa 123"},
}
CARLOS = {"id": 2, "nombre": "Carlos Ruiz", "email": "carlos.ruiz@example.com", "ficha": None}
EMAIL_REPETIDO = {"detail": "Ya existe un dueño con ese email"}
NO_EXISTE = {"detail": "No existe el dueño"}


async def test_obtener_duenio_con_ficha_responde_200_con_la_ficha(base_con_seed, client):
    r = await client.get("/duenios/1")

    assert r.status_code == 200
    assert r.json() == ANA


async def test_obtener_duenio_sin_ficha_responde_ficha_null(base_con_seed, client):
    r = await client.get("/duenios/2")

    assert r.status_code == 200
    assert r.json() == CARLOS


async def test_obtener_duenio_inexistente_responde_404(base_con_seed, client):
    r = await client.get("/duenios/999")

    assert r.status_code == 404
    assert r.json() == NO_EXISTE


@pytest.fixture
def espia(monkeypatch):
    """Reemplaza `service.obtener_duenio` por un espía async que registra y delega."""
    from app.modules.duenios import service

    llamadas: list[int] = []
    real = service.obtener_duenio

    async def intermedio(session, duenio_id):
        llamadas.append(duenio_id)
        return await real(session, duenio_id)

    monkeypatch.setattr(service, "obtener_duenio", intermedio)
    return llamadas


async def test_ruta_con_id_no_entero_responde_422_sin_ejecutar_el_handler(
    base_con_seed, client, espia, sentencias_app
):
    sentencias_app.clear()

    r = await client.get("/duenios/abc")

    assert r.status_code == 422
    error = r.json()["detail"][0]
    assert error["loc"] == ["path", "id"]
    assert error["type"] == "int_parsing"
    assert espia == []
    assert sentencias_app == []


async def test_espia_registra_la_llamada_con_id_valido(base_con_seed, client, espia):
    r = await client.get("/duenios/1")

    assert r.status_code == 200
    assert espia == [1]


@pytest.mark.parametrize("id_ruta", ["2147483648", "99999999999"])
async def test_id_sobre_la_cota_responde_422(base_con_seed, client, sentencias_app, id_ruta):
    sentencias_app.clear()

    r = await client.get(f"/duenios/{id_ruta}")

    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["path", "id"]
    assert sentencias_app == []


@pytest.mark.parametrize("id_ruta", ["0", "-1", "2147483647"])
async def test_id_cero_negativo_o_maximo_en_rango_responde_404(base_con_seed, client, id_ruta):
    r = await client.get(f"/duenios/{id_ruta}")

    assert r.status_code == 404
    assert r.json() == NO_EXISTE


async def test_crear_duenio_valido_responde_201(base_con_seed, client):
    cuerpo = {"nombre": "Lucía Fernández", "email": "lucia.fernandez@example.com"}

    r = await client.post("/duenios/", json=cuerpo)

    assert r.status_code == 201
    assert r.json() == {"id": 3, **cuerpo}
    detalle = await client.get("/duenios/3")
    assert detalle.json() == {"id": 3, **cuerpo, "ficha": None}


async def contar(sesion, tabla: str) -> int:
    return (await sesion.exec(text(f"SELECT count(*) FROM {tabla}"))).scalar_one()


async def test_crear_duenio_con_email_repetido_responde_409(base_con_seed, client, sesion):
    r = await client.post("/duenios/", json={"nombre": "Otra Ana", "email": "ana.gomez@example.com"})

    assert r.status_code == 409
    assert r.json() == EMAIL_REPETIDO
    assert await contar(sesion, "duenio") == 2


async def test_crear_duenio_con_dominio_en_otra_capitalizacion_responde_409(base_con_seed, client):
    r = await client.post("/duenios/", json={"nombre": "Otra Ana", "email": "ana.gomez@EXAMPLE.com"})

    assert r.status_code == 409
    assert r.json() == EMAIL_REPETIDO


async def test_crear_duenio_guarda_textos_sin_espacios_y_dominio_en_minusculas(base_con_seed, client):
    r = await client.post(
        "/duenios/", json={"nombre": "  Lucía Fernández  ", "email": "Lucia.Fernandez@EXAMPLE.COM"}
    )

    assert r.status_code == 201
    assert r.json() == {"id": 3, "nombre": "Lucía Fernández", "email": "Lucia.Fernandez@example.com"}


@pytest.mark.parametrize(
    "cuerpo,campo",
    [
        ({"nombre": "Lucía"}, "email"),
        ({"email": "lucia@example.com"}, "nombre"),
        ({"nombre": "Lucía", "email": "no-es-un-email"}, "email"),
        ({"nombre": "   ", "email": "lucia@example.com"}, "nombre"),
        ({"id": 7, "nombre": "Lucía", "email": "lucia@example.com"}, "id"),
    ],
    ids=["sin_email", "sin_nombre", "email_invalido", "nombre_en_blanco", "campo_id"],
)
async def test_crear_duenio_con_cuerpo_invalido_responde_422_y_no_escribe(
    base_con_seed, client, sesion, cuerpo, campo
):
    r = await client.post("/duenios/", json=cuerpo)

    assert r.status_code == 422
    assert [e["loc"] for e in r.json()["detail"]] == [["body", campo]]
    assert await contar(sesion, "duenio") == 2


async def test_despues_de_un_409_la_siguiente_alta_funciona(base_con_seed, client, sesion):
    rechazada = await client.post("/duenios/", json={"nombre": "Otra Ana", "email": "ana.gomez@example.com"})

    r = await client.post("/duenios/", json={"nombre": "Lucía", "email": "lucia@example.com"})

    assert rechazada.status_code == 409
    assert r.status_code == 201
    assert await contar(sesion, "duenio") == 3


async def test_el_409_no_expone_detalles_de_la_base(base_con_seed, client):
    r = await client.post("/duenios/", json={"nombre": "Otra Ana", "email": "ana.gomez@example.com"})

    assert list(r.json()) == ["detail"]
    for prohibido in ("uq_duenio_email", "duplicate key", "INSERT", "asyncpg"):
        assert prohibido not in r.text


async def test_patch_solo_nombre_conserva_el_email_y_la_ficha(base_con_seed, client):
    r = await client.patch("/duenios/1", json={"nombre": "Ana María Gómez"})

    assert r.status_code == 200
    assert r.json() == {**ANA, "nombre": "Ana María Gómez"}


@pytest.mark.parametrize(
    "duenio_id,cuerpo,esperado",
    [
        (2, {"email": "carlos.ruiz@example.org"}, {**CARLOS, "email": "carlos.ruiz@example.org"}),
        (2, {}, CARLOS),
        (1, {"email": "ana.gomez@example.com"}, ANA),
    ],
    ids=["solo_email", "cuerpo_vacio", "propio_email"],
)
async def test_patch_aplica_solo_lo_enviado(base_con_seed, client, duenio_id, cuerpo, esperado):
    r = await client.patch(f"/duenios/{duenio_id}", json=cuerpo)

    assert r.status_code == 200
    assert r.json() == esperado
    assert (await client.get(f"/duenios/{duenio_id}")).json() == esperado


async def test_patch_de_duenio_inexistente_responde_404_y_no_crea_nada(base_con_seed, client, sesion):
    r = await client.patch("/duenios/999", json={"nombre": "Nadie"})

    assert r.status_code == 404
    assert r.json() == NO_EXISTE
    assert await contar(sesion, "duenio") == 2


async def test_patch_con_email_de_otro_duenio_responde_409_y_no_cambia_nada(base_con_seed, client):
    r = await client.patch("/duenios/2", json={"nombre": "Carlos R.", "email": "ana.gomez@example.com"})

    assert r.status_code == 409
    assert r.json() == EMAIL_REPETIDO
    assert (await client.get("/duenios/2")).json() == CARLOS


@pytest.mark.parametrize("cuerpo", [{"nombre": None}, {"email": None}], ids=["nombre_null", "email_null"])
async def test_patch_con_null_responde_422(base_con_seed, client, cuerpo):
    r = await client.patch("/duenios/2", json=cuerpo)

    assert r.status_code == 422
    assert (await client.get("/duenios/2")).json() == CARLOS


@pytest.mark.parametrize(
    "cuerpo",
    [{"email": "no-es-un-email"}, {"nombre": ""}, {"id": 5}],
    ids=["email_invalido", "nombre_vacio", "campo_id"],
)
async def test_patch_con_cuerpo_invalido_responde_422_y_no_cambia_nada(base_con_seed, client, cuerpo):
    r = await client.patch("/duenios/2", json=cuerpo)

    assert r.status_code == 422
    assert (await client.get("/duenios/2")).json() == CARLOS


FICHA_2 = {"telefono": "11 5555-0202", "direccion": "Av. Siempre Viva 742"}


async def test_crear_ficha_para_duenio_sin_ficha_responde_201(base_con_seed, client):
    r = await client.post("/duenios/2/ficha", json=FICHA_2)

    assert r.status_code == 201
    assert r.json() == {"id": 2, "duenio_id": 2, **FICHA_2}
    assert (await client.get("/duenios/2")).json()["ficha"] == r.json()


async def test_segunda_ficha_responde_409_y_conserva_la_primera(base_con_seed, client):
    r = await client.post("/duenios/1/ficha", json={"telefono": "11 5555-9999", "direccion": "Otra dirección 1"})

    assert r.status_code == 409
    assert r.json() == {"detail": "El dueño ya tiene una ficha"}
    assert (await client.get("/duenios/1")).json()["ficha"] == ANA["ficha"]


async def test_ficha_de_duenio_inexistente_responde_404(base_con_seed, client, sesion):
    r = await client.post("/duenios/999/ficha", json={"telefono": "11 5555-0999", "direccion": "Calle 999"})

    assert r.status_code == 404
    assert r.json() == NO_EXISTE
    assert await contar(sesion, "ficha_duenio") == 1


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"telefono": "11 5555-0202"},
        {"telefono": "", "direccion": "Av. Siempre Viva 742"},
        {"duenio_id": 1, **FICHA_2},
    ],
    ids=["sin_direccion", "telefono_vacio", "con_duenio_id"],
)
async def test_crear_ficha_con_cuerpo_invalido_responde_422_y_no_escribe(base_con_seed, client, sesion, cuerpo):
    r = await client.post("/duenios/2/ficha", json=cuerpo)

    assert r.status_code == 422
    assert (await client.get("/duenios/2")).json()["ficha"] is None
    assert await contar(sesion, "ficha_duenio") == 1


TOBY = {"id": 1, "nombre": "Toby", "especie": "perro", "duenio_id": 1}
MISHI = {"id": 2, "nombre": "Mishi", "especie": "gato", "duenio_id": 1}
LUNA = {"id": 3, "nombre": "Luna", "especie": "perro", "duenio_id": 2}


async def test_mascotas_de_duenio_con_dos_mascotas(base_con_seed, client):
    r = await client.get("/duenios/1/mascotas")

    assert r.status_code == 200
    assert r.json() == [TOBY, MISHI]


async def test_mascotas_de_duenio_con_una_mascota(base_con_seed, client):
    r = await client.get("/duenios/2/mascotas")

    assert r.status_code == 200
    assert r.json() == [LUNA]


async def test_mascotas_de_duenio_recien_creado_es_lista_vacia(base_con_seed, client):
    await client.post("/duenios/", json={"nombre": "Lucía", "email": "lucia@example.com"})

    r = await client.get("/duenios/3/mascotas")

    assert r.status_code == 200
    assert r.json() == []


async def test_mascotas_de_duenio_inexistente_responde_404(base_con_seed, client):
    r = await client.get("/duenios/999/mascotas")

    assert r.status_code == 404
    assert r.json() == NO_EXISTE


async def test_mascotas_se_ordenan_por_id_aunque_el_alfabeto_difiera(base_con_seed, client, sesion):
    await sesion.exec(text("INSERT INTO duenio (nombre, email) VALUES ('Z', 'z@example.com')"))
    await sesion.exec(
        text(
            "INSERT INTO mascota (nombre, especie, duenio_id) VALUES "
            "('Zeta', 'perro', 3), ('Alfa', 'gato', 3), ('Mono', 'perro', 3)"
        )
    )
    await sesion.commit()

    r = await client.get("/duenios/3/mascotas")

    assert [m["id"] for m in r.json()] == [4, 5, 6]
    assert [m["nombre"] for m in r.json()] == ["Zeta", "Alfa", "Mono"]


async def test_borrar_duenio_sin_mascotas_ni_ficha_responde_204(base_con_seed, client, sesion):
    await client.post("/duenios/", json={"nombre": "Lucía", "email": "lucia@example.com"})

    r = await client.delete("/duenios/3")

    assert r.status_code == 204
    assert r.content == b""
    ids = (await sesion.exec(text("SELECT id FROM duenio ORDER BY id"))).scalars().all()
    assert ids == [1, 2]


async def test_borrar_duenio_inexistente_responde_404(base_con_seed, client, sesion):
    r = await client.delete("/duenios/999")

    assert r.status_code == 404
    assert r.json() == NO_EXISTE
    assert await contar(sesion, "duenio") == 2


async def test_borrar_dos_veces_el_mismo_duenio_responde_204_y_luego_404(base_con_seed, client):
    await client.post("/duenios/", json={"nombre": "Lucía", "email": "lucia@example.com"})

    primera = await client.delete("/duenios/3")
    segunda = await client.delete("/duenios/3")

    assert primera.status_code == 204
    assert segunda.status_code == 404
    assert segunda.json() == NO_EXISTE


async def test_borrar_duenio_con_mascotas_responde_409_y_no_borra_nada(base_con_seed, client, sesion):
    r = await client.delete("/duenios/1")

    assert r.status_code == 409
    assert r.json() == {"detail": "No se puede borrar el dueño: tiene mascotas a su nombre"}
    assert await contar(sesion, "duenio") == 2
    assert await contar(sesion, "ficha_duenio") == 1
    assert (await sesion.exec(text("SELECT id FROM mascota WHERE duenio_id = 1 ORDER BY id"))).scalars().all() == [1, 2]


async def test_borrar_duenio_con_ficha_y_sin_mascotas_borra_la_ficha(base_con_seed, client, sesion):
    await client.post("/duenios/", json={"nombre": "Lucía", "email": "lucia@example.com"})
    await client.post("/duenios/3/ficha", json=FICHA_2)

    r = await client.delete("/duenios/3")

    assert r.status_code == 204
    assert (await client.get("/duenios/3")).status_code == 404
    huerfanas = (await sesion.exec(text("SELECT count(*) FROM ficha_duenio WHERE duenio_id = 3"))).scalar_one()
    assert huerfanas == 0


@pytest.mark.parametrize(
    "metodo,ruta,cuerpo",
    [
        ("PATCH", "/duenios/abc", {"nombre": "X"}),
        ("DELETE", "/duenios/abc", None),
        ("POST", "/duenios/abc/ficha", FICHA_2),
        ("GET", "/duenios/abc/mascotas", None),
    ],
    ids=["patch", "delete", "ficha", "mascotas"],
)
async def test_id_no_entero_responde_422_en_todas_las_rutas(base_con_seed, client, sesion, metodo, ruta, cuerpo):
    r = await client.request(metodo, ruta, json=cuerpo)

    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["path", "id"]
    assert await contar(sesion, "duenio") == 2
    assert await contar(sesion, "ficha_duenio") == 1
    assert await contar(sesion, "mascota") == 3
    assert (await client.get("/duenios/1")).json() == ANA


async def test_openapi_declara_los_codigos_de_la_consigna(base_con_seed, client):
    esquema = (await client.get("/openapi.json")).json()
    rutas = esquema["paths"]
    esperado = {
        ("/duenios/", "post"): {"201", "409", "422"},
        ("/duenios/{id}", "get"): {"200", "404", "422"},
        ("/duenios/{id}", "patch"): {"200", "404", "409", "422"},
        ("/duenios/{id}", "delete"): {"204", "404", "409", "422"},
        ("/duenios/{id}/ficha", "post"): {"201", "404", "409", "422"},
        ("/duenios/{id}/mascotas", "get"): {"200", "404", "422"},
    }
    for (ruta, metodo), codigos in esperado.items():
        respuestas = rutas[ruta][metodo]["responses"]
        assert codigos <= set(respuestas), (ruta, metodo)
        for codigo in codigos & {"404", "409"}:
            assert respuestas[codigo]["content"]["application/json"]["schema"]["$ref"].endswith("/MensajeError")


def test_handlers_de_duenios_son_async():
    import inspect

    from app.modules.duenios.router import router

    assert len(router.routes) == 6
    assert all(inspect.iscoroutinefunction(ruta.endpoint) for ruta in router.routes)
