# Construcción y publicación

## Requisitos de distribución

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

## Seguridad y publicación

Antes de una versión estable, revisa [SECURITY.md](../SECURITY.md), habilita GitHub Private Vulnerability Reporting y confirma que los reportes puedan recibirse por un canal privado. No publiques una versión estable mientras ese canal no esté disponible.

## Publicación

`.github/workflows/publish.yml` publica automáticamente cuando se publica un GitHub Release:

- Release marcada como **pre-release** → TestPyPI.
- Release estable → PyPI.

El workflow comprueba que la etiqueta sea exactamente `v<project.version>`, construye los artefactos una sola vez y publica esos mismos artefactos. Utiliza PyPI Trusted Publishing (OIDC); no requiere un token API persistente.

### Configuración de Trusted Publishing

Configura dos publishers, uno en TestPyPI y otro en PyPI, con:

| Campo | TestPyPI | PyPI |
|---|---|---|
| Owner | `specter327` | `specter327` |
| Repository | `fscryptography` | `fscryptography` |
| Workflow | `publish.yml` | `publish.yml` |
| Environment | `testpypi` | `pypi` |

Crea también los GitHub Environments `testpypi` y `pypi`. Se recomienda proteger el environment `pypi` con aprobación requerida antes de publicar una versión estable.

Para el primer registro del nombre en PyPI, configura un **pending publisher** si la interfaz de PyPI lo permite para el proyecto aún no creado. El primer release debe publicarse primero en TestPyPI y verificarse antes de crear el release estable en GitHub.

### Secuencia de release

1. Confirmar que el titular y el aviso de copyright de `LICENSE` son correctos para la titularidad legal del proyecto.
2. Actualizar `project.version` en `pyproject.toml` y `__version__` en `src/fscryptography/__init__.py` al mismo valor.
3. Actualizar notas de versión y validar el cambio mediante CI.
4. Crear una etiqueta anotada `vX.Y.Z` que apunte al commit integrado.
5. Crear un GitHub Release marcado como pre-release para publicar en TestPyPI.
6. Verificar instalación, metadatos, wheel/sdist y funcionamiento desde TestPyPI en un entorno limpio.
7. Crear el GitHub Release estable correspondiente para publicar en PyPI.

PyPI no permite reemplazar un archivo ya publicado para una misma versión. Si un artefacto tiene un defecto, corrige el código y publica una versión nueva.

## Condiciones previas a la primera publicación

- [ ] Verificar la identidad legal del titular reflejada en el aviso de copyright.
- [ ] Configurar los dos Trusted Publishers y los GitHub Environments.
- [ ] Confirmar que el nombre `fscryptography` está disponible en PyPI.
- [ ] Ejecutar el flujo completo en TestPyPI.
- [ ] Revisar la versión, notas de release y compatibilidad declarada.
