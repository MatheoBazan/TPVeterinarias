import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integracion

TOBY = {"id": 1, "nombre": "Toby", "especie": "perro", "duenio_id": 1}
MISHI = {"id": 2, "nombre": "Mishi", "especie": "gato", "duenio_id": 1}
LUNA = {"id": 3, "nombre": "Luna", "especie": "perro", "duenio_id": 2}
ANA = {"id": 1, "nombre": "Ana Gómez", "email": "ana.gomez@example.com"}
CARLOS = {"id": 2, "nombre": "Carlos Ruiz", "email": "carlos.ruiz@example.com"}


async def contar_mascotas(sesion) -> int:
    return (await sesion.exec(text("SELECT count(*) FROM mascota"))).scalar_one()


# --- Detalle (GET /mascotas/{id}) ---


@pytest.mark.parametrize(
    "mascota_id,mascota,duenio",
    [(1, TOBY, ANA), (3, LUNA, CARLOS)],
    ids=["toby_de_ana", "luna_de_carlos"],
)
async def test_obtener_mascota_responde_200_con_su_duenio(base_con_seed, client, mascota_id, mascota, duenio):
    r = await client.get(f"/mascotas/{mascota_id}")

    assert r.status_code == 200
    assert r.json() == {**mascota, "duenio": duenio}


@pytest.mark.parametrize("mascota_id", [999, 0, 2147483647])
async def test_obtener_mascota_inexistente_responde_404(base_con_seed, client, mascota_id):
    r = await client.get(f"/mascotas/{mascota_id}")

    assert r.status_code == 404
    assert r.json() == {"detail": "No existe la mascota"}


@pytest.mark.parametrize(
    "valor,tipo",
    [("abc", "int_parsing"), ("2147483648", "less_than_equal")],
)
async def test_obtener_mascota_con_id_invalido_responde_422(base_con_seed, client, valor, tipo):
    r = await client.get(f"/mascotas/{valor}")

    assert r.status_code == 422
    (error,) = r.json()["detail"]
    assert error["loc"] == ["path", "id"]
    assert error["type"] == tipo


async def test_mascotas_del_duenio_siguen_iguales(base_con_seed, client):
    r = await client.get("/duenios/1/mascotas")

    assert r.status_code == 200
    assert r.json() == [TOBY, MISHI]


# --- Alta (POST /mascotas/) ---


async def test_crear_mascota_valida_responde_201(base_con_seed, client):
    r = await client.post("/mascotas/", json={"nombre": "Rocky", "especie": "perro", "duenio_id": 2})

    assert r.status_code == 201
    rocky = {"id": 4, "nombre": "Rocky", "especie": "perro", "duenio_id": 2}
    assert r.json() == rocky
    r2 = await client.get("/duenios/2/mascotas")
    assert r2.status_code == 200
    assert r2.json() == [LUNA, rocky]


async def test_crear_mascota_guarda_los_textos_sin_espacios(base_con_seed, client, sesion_seed):
    r = await client.post("/mascotas/", json={"nombre": "  Pelusa  ", "especie": " gato ", "duenio_id": 1})

    assert r.status_code == 201
    assert r.json()["nombre"] == "Pelusa"
    assert r.json()["especie"] == "gato"
    fila = (await sesion_seed.exec(text("SELECT nombre, especie FROM mascota WHERE id = 4"))).one()
    assert tuple(fila) == ("Pelusa", "gato")


# --- Alta con dueño inexistente (caso C-04, primera parte) ---

FANTASMA = {"nombre": "Fantasma", "especie": "gato", "duenio_id": 999}


async def test_crear_mascota_con_duenio_inexistente_responde_409(base_con_seed, client, sesion_seed):
    r = await client.post("/mascotas/", json=FANTASMA)

    assert r.status_code == 409
    assert r.json() == {"detail": "No existe el dueño indicado"}
    for filtrado in ("mascota_duenio_id_fkey", "foreign key", "INSERT", "asyncpg"):
        assert filtrado not in r.text
    assert await contar_mascotas(sesion_seed) == 3


@pytest.mark.parametrize("duenio_id", [0, -1])
async def test_crear_mascota_con_duenio_cero_o_negativo_responde_409(base_con_seed, client, sesion_seed, duenio_id):
    r = await client.post("/mascotas/", json={**FANTASMA, "duenio_id": duenio_id})

    assert r.status_code == 409
    assert r.json() == {"detail": "No existe el dueño indicado"}
    assert await contar_mascotas(sesion_seed) == 3


async def test_despues_de_un_409_la_siguiente_alta_funciona(base_con_seed, client, sesion_seed):
    rechazada = await client.post("/mascotas/", json=FANTASMA)
    aceptada = await client.post("/mascotas/", json={"nombre": "Rocky", "especie": "perro", "duenio_id": 2})

    assert rechazada.status_code == 409
    assert aceptada.status_code == 201
    assert await contar_mascotas(sesion_seed) == 4


# --- Contrato de entrada del alta ---

VALIDA = {"nombre": "Rocky", "especie": "perro", "duenio_id": 1}


def _sin(campo: str) -> dict:
    return {k: v for k, v in VALIDA.items() if k != campo}


@pytest.mark.parametrize(
    "cuerpo,loc,tipo",
    [
        (_sin("nombre"), ["body", "nombre"], "missing"),
        (_sin("especie"), ["body", "especie"], "missing"),
        (_sin("duenio_id"), ["body", "duenio_id"], "missing"),
        ({**VALIDA, "nombre": "   "}, ["body", "nombre"], "string_too_short"),
        ({**VALIDA, "especie": ""}, ["body", "especie"], "string_too_short"),
        ({**VALIDA, "duenio_id": "abc"}, ["body", "duenio_id"], "int_parsing"),
        ({**VALIDA, "duenio_id": 2147483648}, ["body", "duenio_id"], "less_than_equal"),
        ({**VALIDA, "id": 9}, ["body", "id"], "extra_forbidden"),
    ],
    ids=[
        "falta_nombre",
        "falta_especie",
        "falta_duenio_id",
        "nombre_en_blanco",
        "especie_vacia",
        "duenio_id_no_entero",
        "duenio_id_sobre_int4",
        "campo_id",
    ],
)
async def test_crear_mascota_con_cuerpo_invalido_responde_422(base_con_seed, client, sesion_seed, cuerpo, loc, tipo):
    r = await client.post("/mascotas/", json=cuerpo)

    assert r.status_code == 422
    assert any(e["loc"] == loc and e["type"] == tipo for e in r.json()["detail"]), r.json()
    assert await contar_mascotas(sesion_seed) == 3
