# fscryptography

**fscryptography** (*filesystem-cryptography*) es una librería Python para cifrar y descifrar archivos y nombres de archivos y directorios directamente sobre rutas del sistema de archivos.

Proporciona una API de alto nivel basada en rutas, cifrado autenticado y procesamiento segmentado para archivos grandes. No depende de herramientas de exploración de recursos ni de aplicaciones concretas.

## Instalación

Requiere Python 3.11 o posterior.

```bash
python -m pip install fscryptography
```

## Inicio rápido

```python
from pathlib import Path

import fscryptography

# Genera una clave maestra aleatoria codificada en Base64.
master_key = fscryptography.generate()

# Guarda la clave de forma segura fuera del directorio que se cifra.
# Quien obtenga la clave podrá descifrar los recursos protegidos.

with fscryptography.Manager(key=master_key) as manager:
    manager.file.encrypt(Path("document.txt"))
    manager.file.decrypt(Path("document.fscrypt"))
```

Para proteger el contenedor de clave maestra con contraseña:

```python
master_key = fscryptography.generate(password="correct horse battery staple")

with fscryptography.Manager(
    key=master_key,
    password="correct horse battery staple",
) as manager:
    manager.file.encrypt("confidential.pdf", encrypt_name=True)
```

La contraseña se consume al abrir el contenedor y no se conserva en el gestor. No debe confundirse la contraseña con una copia de seguridad de la clave: conserva la cadena Base64 de la MasterKey en un lugar seguro.

## API principal

```python
import fscryptography

master_key = fscryptography.generate()
# O bien: fscryptography.generate(password="...")

manager = fscryptography.Manager(key=master_key)
# Para una MasterKey protegida: Manager(key=master_key, password="...")

manager.file.encrypt("report.txt")
manager.file.encrypt("archive.tar.gz", new_extension=".locked")
manager.file.encrypt("private.txt", encrypt_name=True)
manager.file.decrypt("report.fscrypt")

manager.dir.encrypt("private-directory")
manager.dir.decrypt("~1...")

records = manager.inspect_recovery("/path/to/parent")  # Inspección de solo lectura
exported_key = manager.export_key()
manager.close()
```

Las operaciones de directorio transforman exclusivamente el nombre del directorio: **no recorren ni cifran su contenido**. La librería no ofrece una API pública de cifrado genérico de bytes o streams.

## Diseño criptográfico

- Google Tink para Streaming AEAD de contenido (`AES256_GCM_HKDF_1MB`) y AEAD de nombres (`AES256_GCM`).
- Argon2id y AES-256-GCM para proteger una MasterKey cuando se especifica contraseña.
- Keysets independientes para contenido y nombres.
- Formatos versionados y metadata de archivo autenticada.
- Operaciones de filesystem diseñadas para evitar sobrescrituras accidentales y preservar información de transacciones interrumpidas.

## Compatibilidad y límites

- Python 3.11+.
- GNU/Linux y Windows.
- En GNU/Linux se utilizan operaciones relativas a descriptores de directorio y publicación no-replace cuando el sistema las soporta.
- En Windows existen diferencias documentadas: no se ofrece el mismo anclaje de directorio ni la misma garantía de cuarentena del origen.
- No se garantiza protección frente a procesos hostiles que operen bajo el mismo UID/usuario.
- Las semánticas de durabilidad y renombrado de sistemas de archivos alternativos o de red no están validadas exhaustivamente.

La inspección del journal es explícita y de solo lectura. No hay recuperación destructiva ni limpieza automática de transacciones completadas.

## Seguridad

Esta librería manipula claves criptográficas y archivos del usuario. Revisa el [modelo de seguridad](docs/security-model.md), la [política de gestión de claves](docs/key-management.md), la [compatibilidad de plataformas](docs/platform-compatibility.md) y la [documentación técnica](docs/index.md) antes de integrarla en un flujo sensible.

La protección criptográfica no sustituye las copias de seguridad, el control de acceso del sistema operativo ni una política de gestión y rotación de claves. La implementación y sus pruebas automatizadas no equivalen a una auditoría criptográfica independiente.

## Desarrollo

Instala las dependencias de desarrollo:

```bash
python -m pip install -e ".[dev]"
```

Ejecuta las pruebas:

```bash
python -m pytest
```

Construye y valida los artefactos de distribución:

```bash
python -m build
python -m twine check dist/*
```

El proyecto utiliza un diseño `src/` y publica un wheel y un source distribution (sdist). La publicación a PyPI se automatiza mediante GitHub Actions y Trusted Publishing (OIDC); no requiere almacenar un token PyPI de larga duración en los secretos del repositorio.

## Estado

Versión inicial de distribución: **0.1.0**. El proyecto continúa en fase alpha. Consulta [GitHub Releases](https://github.com/specter327/fscryptography/releases) para conocer las versiones publicadas y sus notas.

## Documentación

La documentación normativa y técnica está en [docs/](docs/index.md). El [contrato de API](docs/api-reference.md) describe las operaciones, retornos y excepciones.
