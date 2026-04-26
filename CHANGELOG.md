# Changelog

## 1.1.0 - Seguridad, respaldos y busqueda

- Agrega respaldos automaticos diarios y semanales de `finanzas.db` en la carpeta `backups/`.
- Agrega respaldo manual desde la interfaz.
- Obliga a cambiar la contrasena inicial `admin123` antes de usar la app.
- Cierra sesion automaticamente tras 15 minutos sin actividad.
- Agrega modo privacidad para ocultar saldos y difuminar graficas.
- Agrega busqueda rapida de gastos por monto, fecha, categoria, metodo o descripcion.
- Mejora `iniciar_app.bat` para crear `.venv`, instalar dependencias, abrir el navegador y arrancar Flask.
- Actualiza `.gitignore` para evitar subir respaldos, base de datos y entornos locales.

## 1.0.0 - Primera version

- Crea app local con Flask, SQLite, HTML, CSS y JavaScript.
- Agrega login local, dashboard, gastos, ingresos, tarjetas y calendario.
- Agrega categorias, subcategorias, tema claro/oscuro, exportacion Excel y respaldo/restauracion `.db`.
