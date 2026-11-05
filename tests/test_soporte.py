import pytest
from soporte import validar_url_de_test

URL_TEST = "postgresql+asyncpg://u:p@localhost:5433/veterinaria_test"


def test_validar_url_de_test_sin_url_falla_nombrando_variable_y_env_example():
    with pytest.raises(pytest.fail.Exception) as error:
        validar_url_de_test(None)

    assert "TEST_DATABASE_URL" in str(error.value)
    assert "env.example" in str(error.value)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@localhost:5433/veterinaria",
        "postgresql+asyncpg://u:p@localhost:5433/postgres",
    ],
)
def test_validar_url_de_test_con_base_que_no_termina_en_test_exige_el_sufijo(url):
    with pytest.raises(pytest.fail.Exception) as error:
        validar_url_de_test(url)

    assert "_test" in str(error.value)


@pytest.mark.parametrize(
    "url",
    [URL_TEST, "postgresql+asyncpg://otro:x@127.0.0.1:5432/otra_test"],
)
def test_validar_url_de_test_con_base_de_test_devuelve_la_misma_url(url):
    assert validar_url_de_test(url) == url
