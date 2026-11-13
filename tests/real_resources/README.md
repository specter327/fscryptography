# Pruebas de integración sobre recursos reales

`test_real_resources.py` ejecuta operaciones de extremo a extremo mediante la API pública.
No usa mocks para las operaciones de filesystem: crea y transforma archivos y directorios
reales bajo `tests/resources/runs/`.

Incluye round-trips de archivos vacíos, UTF-8 y binarios grandes; extensiones personalizadas;
cifrado de nombres; cifrado de nombres de directorios sin recorrer su contenido; preservación
ante conflictos; detección de alteraciones autenticadas; inspección del journal; sustitución
de clave y apertura de una MasterKey protegida por contraseña.

La suite conserva cada ejecución en una carpeta única. No elimina automáticamente los
recursos, ni toca archivos que existían antes de iniciar la prueba.

Instala el paquete en modo editable con sus dependencias de prueba:

```bash
python -m pip install -e ".[test]"
```

Comandos:

```bash
python tests/real_resources/test_real_resources.py
python -m pytest -s -v tests/real_resources
```

La suite se ejecuta en CI sobre Ubuntu y Windows, con CPython 3.11, 3.12 y 3.13.
