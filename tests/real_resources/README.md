# Pruebas de integración sobre recursos reales

`test_real_resources.py` ejecuta operaciones de extremo a extremo mediante la API pública.
No usa mocks para las operaciones de filesystem: crea y transforma archivos y directorios
reales bajo `tests/resources/runs/`.

Incluye round-trips de archivos vacíos, UTF-8 y binarios grandes; extensiones personalizadas;
cifrado de nombres; cifrado de nombres de directorios sin recorrer su contenido; preservación
ante conflictos; detección de alteraciones autenticadas; inspección del journal; y sustitución
de la clave activa.

La suite conserva cada ejecución en una carpeta única. No elimina automáticamente los
recursos, ni toca archivos que existían antes de iniciar la prueba.

Comandos:

```bash
python tests/real_resources/test_real_resources.py
python -m pytest -s -v tests/real_resources
```
