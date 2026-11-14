# Construcción y publicación

## Requisitos de distribución

El historial público de cambios vive en [CHANGELOG.md](../CHANGELOG.md); las reglas de compatibilidad de API y formatos viven en [versioning.md](versioning.md).

El proyecto usa el backend PEP 517 de setuptools y el layout `src/`. El nombre de distribución y el nombre importable son ambos `fscryptography`.

- Wheel: `fscryptography-<version>-py3-none-any.whl`.
- Source distribution: `fscryptography-<version>.tar.gz`.
- Python mínimo: 3.11.
- Dependencias de ejecución: Tink, argon2-cffi y cryptography.
- `py.typed` se incluye en el wheel para declarar el paquete como tipado (PEP 561).
- `MANIFEST.in` incorpora la licencia y la documentación Markdown al sdist.
- La metadata declara `LicenseRef-Proprietary` y empaqueta `LICENSE` mediante PEP 639.

## Construcción local

Desde la raíz del repositorio:

```bash
python -m pip install --upgrade build twine
rm -rf build dist *.egg-info
python -m build
python -m twine check --strict dist/*
```

Para probar el wheel fuera del checkout:

```bash
python -m venv /tmp/fscryptography-wheel-test
/tmp/fscryptography-wheel-test/bin/python -m pip install dist/fscryptography-*.whl
cd /tmp
/tmp/fscryptography-wheel-test/bin/python -c "import fscryptography; print(fscryptography.__version__)"
```

En Windows, crea el entorno virtual con `py -m venv .venv` y utiliza `.venv\\Scripts\\python.exe`.

## CI de distribución

`.github/workflows/distribution.yml` construye ambos formatos en cada PR o push que afecte al paquete, valida los metadatos con Twine, instala el wheel construido fuera del checkout, ejecuta una prueba de humo y corre las pruebas unitarias/formato. Los artefactos quedan disponibles como artifact de GitHub Actions.

Este workflow valida los artefactos; **no los publica**.

## Seguridad y publicación

Antes de una versión estable, revisa [SECURITY.md](../SECURITY.md) y confirma que los reportes de vulnerabilidades puedan recibirse por un canal privado. No publiques una versión estable mientras no exista un canal adecuado para recibir y gestionar reportes de seguridad.

## Publicación manual con Twine

La publicación se realiza manualmente desde un entorno controlado del mantenedor. GitHub Actions no publica a TestPyPI ni a PyPI, y crear un GitHub Release no dispara una subida.

### Preparar artefactos

1. Integra y verifica en `main` los cambios que se van a distribuir.
2. Comprueba que `project.version` en `pyproject.toml` y `__version__` en `src/fscryptography/__init__.py` coincidan.
3. Actualiza `CHANGELOG.md` y revisa la compatibilidad de API y formatos.
4. Construye desde un checkout limpio del commit que se pretende publicar:

```bash
git status --short
python -m pip install --upgrade build twine
rm -rf build dist *.egg-info
python -m build
python -m twine check --strict dist/*
sha256sum dist/*
```

5. Instala el wheel en un entorno virtual nuevo fuera del checkout y ejecuta una prueba de importación y humo. Conserva los nombres y hashes SHA-256 de los artefactos publicados.

### Subida de prueba (recomendada)

Configura un token de TestPyPI de forma segura en el entorno del proceso. No lo escribas en el repositorio, en scripts, ni en la línea de comandos que quede guardada en el historial.

```bash
export TWINE_USERNAME=__token__
read -rsp "TestPyPI API token: " TWINE_PASSWORD; echo
export TWINE_PASSWORD
python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

Verifica la instalación en un entorno limpio. TestPyPI no contiene necesariamente todas las dependencias del paquete; usa PyPI como índice adicional para resolverlas:

```bash
python -m venv /tmp/fscryptography-testpypi
/tmp/fscryptography-testpypi/bin/python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  fscryptography
/tmp/fscryptography-testpypi/bin/python -c "import fscryptography; print(fscryptography.__version__)"
```

### Publicación en PyPI

Una vez aprobados los artefactos y la prueba de instalación, configura un token de PyPI como variable de entorno y sube **los mismos archivos** que se validaron:

```bash
export TWINE_USERNAME=__token__
read -rsp "PyPI API token: " TWINE_PASSWORD; echo
export TWINE_PASSWORD
python -m twine upload dist/*
```

Después, comprueba en la página del proyecto que wheel y sdist aparecen para la versión esperada y realiza una instalación limpia desde PyPI.

Elimina las variables de entorno del shell al terminar:

```bash
unset TWINE_USERNAME TWINE_PASSWORD
```

PyPI no permite reemplazar un archivo ya publicado para una misma versión. Si un artefacto tiene un defecto, corrige el código y publica una versión nueva. Nunca reconstruyas silenciosamente un artefacto distinto bajo una versión ya publicada.

### Etiquetado y registro

Después de verificar la publicación, crea una etiqueta anotada `vX.Y.Z` que apunte al commit realmente distribuido y registra la versión publicada en las notas de GitHub Release. La etiqueta y el GitHub Release documentan la distribución; no ejecutan la subida.

## Lista de verificación

- [ ] Versión del paquete y `__version__` coinciden.
- [ ] CHANGELOG y documentación revisados.
- [ ] Checkout limpio y commit integrado identificados.
- [ ] Wheel y sdist construidos y validados con Twine.
- [ ] Instalación y prueba de humo fuera del checkout aprobadas.
- [ ] Hashes SHA-256 registrados.
- [ ] Artefactos probados en TestPyPI (recomendado).
- [ ] Los mismos artefactos subidos manualmente a PyPI.
- [ ] Wheel, sdist y versión verificados en PyPI.
- [ ] Tag anotado y GitHub Release asociados al commit distribuido.
