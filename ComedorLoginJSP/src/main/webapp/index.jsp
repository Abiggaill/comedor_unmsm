<%@ page contentType="text/html; charset=UTF-8" pageEncoding="UTF-8" %>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Iniciar sesión - Comedor UNMSM</title>
    <link rel="stylesheet" href="resources/css/login.css">
</head>
<body>
    <main class="auth-container">
        <section class="card" aria-labelledby="page-title">
            <div class="brand-mark" aria-hidden="true">UNMSM</div>
            <h1 id="page-title">Comedor UNMSM</h1>
            <h2>Iniciar sesión</h2>

            <form class="login-form">
                <div class="form-group">
                    <label for="correo">Correo institucional:</label>
                    <input type="email" id="correo" name="correo"
                           placeholder="usuario@unmsm.edu.pe"
                           autocomplete="username" required>
                </div>

                <div class="form-group">
                    <label for="password">Contraseña:</label>
                    <input type="password" id="password" name="password"
                           autocomplete="current-password" required>
                </div>

                <button type="button" class="btn-primary">Ingresar</button>
            </form>

            <p class="stage-note">
                Esta pantalla es solo el diseño. La comprobación del usuario se hará en una etapa posterior.
            </p>
            <hr>
            <p class="text-center">¿No tienes una cuenta aún?</p>
            <span class="btn-secondary disabled" aria-disabled="true">Registrar cuenta (próximamente)</span>
        </section>
    </main>
</body>
</html>