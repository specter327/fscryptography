# Recursos de integración

Esta carpeta contiene los recursos físicos utilizados por la suite de integración de
`fscryptography`.

- La suite crea archivos vacíos, texto UTF-8, datos binarios de varios MiB y directorios.
- Cada ejecución usa un directorio nuevo dentro de `runs/`.
- Los recursos generados se conservan después de la ejecución para inspección manual.
- `runs/` está excluido de Git; no se versionan resultados generados.
- La suite no selecciona ni modifica archivos preexistentes del usuario.
- No coloques aquí documentos personales ni archivos que contengan secretos.

Instala el proyecto y sus dependencias de prueba desde la raíz del repositorio:

```bash
python -m pip install -e ".[test]"
```

Ejecuta la demostración:

```bash
python tests/real_resources/test_real_resources.py
```

También forma parte de la suite de pytest:

```bash
python -m pytest -s -v tests/real_resources
```

Cada ejecución consume espacio adicional. Elimina manualmente subdirectorios antiguos de
`runs/` cuando ya no necesites conservar sus resultados.
