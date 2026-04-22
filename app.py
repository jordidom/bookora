import os
import uuid
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, send_from_directory
)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
import mysql.connector

app = Flask(__name__)
app.secret_key = "cambia_esto_por_una_clave_segura"

# Configuración MySQL
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""
app.config["MYSQL_DATABASE"] = "bookora"

# Carpetas de subida
app.config["UPLOAD_COVERS"] = os.path.join("static", "uploads", "covers")
app.config["UPLOAD_PDFS"] = os.path.join("static", "uploads", "pdfs")
app.config["UPLOAD_EPUBS"] = os.path.join("static", "uploads", "epubs")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ALLOWED_PDF_EXTENSIONS = {"pdf"}
ALLOWED_EPUB_EXTENSIONS = {"epub"}

for folder in [
    app.config["UPLOAD_COVERS"],
    app.config["UPLOAD_PDFS"],
    app.config["UPLOAD_EPUBS"]
]:
    os.makedirs(folder, exist_ok=True)


def get_db():
    return mysql.connector.connect(
        host=app.config["MYSQL_HOST"],
        user=app.config["MYSQL_USER"],
        password=app.config["MYSQL_PASSWORD"],
        database=app.config["MYSQL_DATABASE"]
    )


def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def save_file(file, folder):
    if not file or file.filename == "":
        return None
    filename = secure_filename(file.filename)
    extension = filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{extension}"
    path = os.path.join(folder, unique_name)
    file.save(path)
    return unique_name


def delete_file_if_exists(folder, filename):
    if filename:
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            os.remove(path)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_id" not in session:
            flash("Debes iniciar sesión como administrador.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
def index():
    busqueda = request.args.get("q", "").strip()
    genero = request.args.get("genero", "").strip()
    idioma = request.args.get("idioma", "").strip()
    anio = request.args.get("anio", "").strip()

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Destacados
    cursor.execute("""
        SELECT libros.*, generos.nombre AS genero_nombre
        FROM libros
        LEFT JOIN generos ON libros.genero_id = generos.id
        WHERE libros.is_featured = 1
        ORDER BY libros.created_at DESC
        LIMIT 6
    """)
    destacados = cursor.fetchall()

    # Libros filtrados
    sql = """
        SELECT libros.*, generos.nombre AS genero_nombre
        FROM libros
        LEFT JOIN generos ON libros.genero_id = generos.id
        WHERE 1=1
    """
    params = []

    if busqueda:
        sql += " AND (libros.titulo LIKE %s OR libros.autor LIKE %s)"
        like_value = f"%{busqueda}%"
        params.extend([like_value, like_value])

    if genero:
        sql += " AND generos.id = %s"
        params.append(genero)

    if idioma:
        sql += " AND libros.idioma = %s"
        params.append(idioma)

    if anio:
        sql += " AND libros.anio_publicacion = %s"
        params.append(anio)

    sql += " ORDER BY libros.is_featured DESC, libros.created_at DESC"

    cursor.execute(sql, params)
    libros = cursor.fetchall()

    cursor.execute("SELECT * FROM generos ORDER BY nombre ASC")
    generos = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT idioma
        FROM libros
        WHERE idioma IS NOT NULL AND idioma != ''
        ORDER BY idioma ASC
    """)
    idiomas = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT anio_publicacion
        FROM libros
        WHERE anio_publicacion IS NOT NULL
        ORDER BY anio_publicacion DESC
    """)
    anios = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "index.html",
        libros=libros,
        destacados=destacados,
        generos=generos,
        idiomas=idiomas,
        anios=anios,
        filtros={
            "q": busqueda,
            "genero": genero,
            "idioma": idioma,
            "anio": anio
        }
    )


@app.route("/libro/<int:libro_id>")
def detalle_libro(libro_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT libros.*, generos.nombre AS genero_nombre
        FROM libros
        LEFT JOIN generos ON libros.genero_id = generos.id
        WHERE libros.id = %s
    """, (libro_id,))
    libro = cursor.fetchone()

    cursor.execute("""
        SELECT id, titulo, autor, portada
        FROM libros
        WHERE id != %s
        ORDER BY is_featured DESC, downloads_count DESC, created_at DESC
        LIMIT 4
    """, (libro_id,))
    relacionados = cursor.fetchall()

    cursor.close()
    conn.close()

    if not libro:
        flash("Libro no encontrado.", "error")
        return redirect(url_for("index"))

    return render_template("detalle_libro.html", libro=libro, relacionados=relacionados)


@app.route("/descargar/pdf/<int:libro_id>")
def descargar_pdf(libro_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT archivo_pdf FROM libros WHERE id = %s", (libro_id,))
    libro = cursor.fetchone()

    if not libro or not libro["archivo_pdf"]:
        cursor.close()
        conn.close()
        flash("Este libro no tiene PDF disponible.", "error")
        return redirect(url_for("detalle_libro", libro_id=libro_id))

    cursor.execute("""
        UPDATE libros
        SET downloads_count = downloads_count + 1
        WHERE id = %s
    """, (libro_id,))
    conn.commit()

    archivo = libro["archivo_pdf"]
    cursor.close()
    conn.close()

    return send_from_directory(
        app.config["UPLOAD_PDFS"],
        archivo,
        as_attachment=True
    )


@app.route("/descargar/epub/<int:libro_id>")
def descargar_epub(libro_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT archivo_epub FROM libros WHERE id = %s", (libro_id,))
    libro = cursor.fetchone()

    if not libro or not libro["archivo_epub"]:
        cursor.close()
        conn.close()
        flash("Este libro no tiene EPUB disponible.", "error")
        return redirect(url_for("detalle_libro", libro_id=libro_id))

    cursor.execute("""
        UPDATE libros
        SET downloads_count = downloads_count + 1
        WHERE id = %s
    """, (libro_id,))
    conn.commit()

    archivo = libro["archivo_epub"]
    cursor.close()
    conn.close()

    return send_from_directory(
        app.config["UPLOAD_EPUBS"],
        archivo,
        as_attachment=True
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if "admin_id" in session:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admins WHERE username = %s", (username,))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()

        if admin and check_password_hash(admin["password"], password):
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            flash("Sesión iniciada correctamente.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Usuario o contraseña incorrectos.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "success")
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT libros.*, generos.nombre AS genero_nombre
        FROM libros
        LEFT JOIN generos ON libros.genero_id = generos.id
        ORDER BY libros.created_at DESC
    """)
    libros = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) AS total_libros FROM libros")
    total_libros = cursor.fetchone()["total_libros"]

    cursor.execute("SELECT COUNT(*) AS total_generos FROM generos")
    total_generos = cursor.fetchone()["total_generos"]

    cursor.execute("SELECT COUNT(*) AS total_destacados FROM libros WHERE is_featured = 1")
    total_destacados = cursor.fetchone()["total_destacados"]

    cursor.execute("SELECT COALESCE(SUM(downloads_count), 0) AS total_descargas FROM libros")
    total_descargas = cursor.fetchone()["total_descargas"]

    cursor.execute("""
        SELECT titulo, autor, downloads_count
        FROM libros
        ORDER BY downloads_count DESC, created_at DESC
        LIMIT 5
    """)
    top_descargados = cursor.fetchall()

    cursor.execute("""
        SELECT generos.nombre AS genero, COUNT(libros.id) AS total
        FROM generos
        LEFT JOIN libros ON libros.genero_id = generos.id
        GROUP BY generos.id, generos.nombre
        ORDER BY total DESC, generos.nombre ASC
        LIMIT 6
    """)
    libros_por_genero = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        libros=libros,
        total_libros=total_libros,
        total_generos=total_generos,
        total_destacados=total_destacados,
        total_descargas=total_descargas,
        top_descargados=top_descargados,
        libros_por_genero=libros_por_genero
    )


@app.route("/admin/libro/nuevo", methods=["GET", "POST"])
@admin_required
def admin_nuevo_libro():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM generos ORDER BY nombre ASC")
    generos = cursor.fetchall()

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        autor = request.form.get("autor", "").strip()
        genero_id = request.form.get("genero_id") or None
        anio_publicacion = request.form.get("anio_publicacion") or None
        idioma = request.form.get("idioma", "").strip()
        editorial = request.form.get("editorial", "").strip()
        paginas = request.form.get("paginas") or None
        sinopsis = request.form.get("sinopsis", "").strip()
        is_featured = 1 if request.form.get("is_featured") == "1" else 0

        portada = request.files.get("portada")
        archivo_pdf = request.files.get("archivo_pdf")
        archivo_epub = request.files.get("archivo_epub")

        if not titulo or not autor:
            flash("Título y autor son obligatorios.", "error")
            cursor.close()
            conn.close()
            return render_template("admin_libro_form.html", generos=generos, libro=None)

        portada_filename = None
        pdf_filename = None
        epub_filename = None

        if portada and portada.filename:
            if not allowed_file(portada.filename, ALLOWED_IMAGE_EXTENSIONS):
                flash("La portada debe ser png, jpg, jpeg o webp.", "error")
                cursor.close()
                conn.close()
                return render_template("admin_libro_form.html", generos=generos, libro=None)
            portada_filename = save_file(portada, app.config["UPLOAD_COVERS"])

        if archivo_pdf and archivo_pdf.filename:
            if not allowed_file(archivo_pdf.filename, ALLOWED_PDF_EXTENSIONS):
                flash("El archivo PDF no es válido.", "error")
                cursor.close()
                conn.close()
                return render_template("admin_libro_form.html", generos=generos, libro=None)
            pdf_filename = save_file(archivo_pdf, app.config["UPLOAD_PDFS"])

        if archivo_epub and archivo_epub.filename:
            if not allowed_file(archivo_epub.filename, ALLOWED_EPUB_EXTENSIONS):
                flash("El archivo EPUB no es válido.", "error")
                cursor.close()
                conn.close()
                return render_template("admin_libro_form.html", generos=generos, libro=None)
            epub_filename = save_file(archivo_epub, app.config["UPLOAD_EPUBS"])

        cursor.execute("""
            INSERT INTO libros (
                titulo, autor, genero_id, anio_publicacion, idioma,
                sinopsis, editorial, paginas, portada, archivo_pdf, archivo_epub, is_featured
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            titulo, autor, genero_id, anio_publicacion, idioma,
            sinopsis, editorial, paginas, portada_filename, pdf_filename, epub_filename, is_featured
        ))
        conn.commit()

        flash("Libro añadido correctamente.", "success")
        cursor.close()
        conn.close()
        return redirect(url_for("admin_dashboard"))

    cursor.close()
    conn.close()
    return render_template("admin_libro_form.html", generos=generos, libro=None)


@app.route("/admin/libro/editar/<int:libro_id>", methods=["GET", "POST"])
@admin_required
def admin_editar_libro(libro_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM generos ORDER BY nombre ASC")
    generos = cursor.fetchall()

    cursor.execute("SELECT * FROM libros WHERE id = %s", (libro_id,))
    libro = cursor.fetchone()

    if not libro:
        cursor.close()
        conn.close()
        flash("Libro no encontrado.", "error")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        autor = request.form.get("autor", "").strip()
        genero_id = request.form.get("genero_id") or None
        anio_publicacion = request.form.get("anio_publicacion") or None
        idioma = request.form.get("idioma", "").strip()
        editorial = request.form.get("editorial", "").strip()
        paginas = request.form.get("paginas") or None
        sinopsis = request.form.get("sinopsis", "").strip()
        is_featured = 1 if request.form.get("is_featured") == "1" else 0

        portada = request.files.get("portada")
        archivo_pdf = request.files.get("archivo_pdf")
        archivo_epub = request.files.get("archivo_epub")

        portada_filename = libro["portada"]
        pdf_filename = libro["archivo_pdf"]
        epub_filename = libro["archivo_epub"]

        if portada and portada.filename:
            if not allowed_file(portada.filename, ALLOWED_IMAGE_EXTENSIONS):
                flash("La portada debe ser png, jpg, jpeg o webp.", "error")
                cursor.close()
                conn.close()
                return render_template("admin_libro_form.html", generos=generos, libro=libro)

            delete_file_if_exists(app.config["UPLOAD_COVERS"], libro["portada"])
            portada_filename = save_file(portada, app.config["UPLOAD_COVERS"])

        if archivo_pdf and archivo_pdf.filename:
            if not allowed_file(archivo_pdf.filename, ALLOWED_PDF_EXTENSIONS):
                flash("El archivo PDF no es válido.", "error")
                cursor.close()
                conn.close()
                return render_template("admin_libro_form.html", generos=generos, libro=libro)

            delete_file_if_exists(app.config["UPLOAD_PDFS"], libro["archivo_pdf"])
            pdf_filename = save_file(archivo_pdf, app.config["UPLOAD_PDFS"])

        if archivo_epub and archivo_epub.filename:
            if not allowed_file(archivo_epub.filename, ALLOWED_EPUB_EXTENSIONS):
                flash("El archivo EPUB no es válido.", "error")
                cursor.close()
                conn.close()
                return render_template("admin_libro_form.html", generos=generos, libro=libro)

            delete_file_if_exists(app.config["UPLOAD_EPUBS"], libro["archivo_epub"])
            epub_filename = save_file(archivo_epub, app.config["UPLOAD_EPUBS"])

        cursor.execute("""
            UPDATE libros
            SET titulo = %s,
                autor = %s,
                genero_id = %s,
                anio_publicacion = %s,
                idioma = %s,
                sinopsis = %s,
                editorial = %s,
                paginas = %s,
                portada = %s,
                archivo_pdf = %s,
                archivo_epub = %s,
                is_featured = %s
            WHERE id = %s
        """, (
            titulo, autor, genero_id, anio_publicacion, idioma,
            sinopsis, editorial, paginas, portada_filename, pdf_filename, epub_filename, is_featured, libro_id
        ))
        conn.commit()

        flash("Libro actualizado correctamente.", "success")
        cursor.close()
        conn.close()
        return redirect(url_for("admin_dashboard"))

    cursor.close()
    conn.close()
    return render_template("admin_libro_form.html", generos=generos, libro=libro)


@app.route("/admin/libro/borrar/<int:libro_id>", methods=["POST"])
@admin_required
def admin_borrar_libro(libro_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM libros WHERE id = %s", (libro_id,))
    libro = cursor.fetchone()

    if libro:
        delete_file_if_exists(app.config["UPLOAD_COVERS"], libro["portada"])
        delete_file_if_exists(app.config["UPLOAD_PDFS"], libro["archivo_pdf"])
        delete_file_if_exists(app.config["UPLOAD_EPUBS"], libro["archivo_epub"])

        cursor.execute("DELETE FROM libros WHERE id = %s", (libro_id,))
        conn.commit()
        flash("Libro eliminado correctamente.", "success")
    else:
        flash("Libro no encontrado.", "error")

    cursor.close()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/generos", methods=["GET", "POST"])
@admin_required
def admin_generos():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if nombre:
            try:
                cursor.execute("INSERT INTO generos (nombre) VALUES (%s)", (nombre,))
                conn.commit()
                flash("Género añadido correctamente.", "success")
            except mysql.connector.Error:
                flash("Ese género ya existe o no se pudo guardar.", "error")
        else:
            flash("El nombre del género es obligatorio.", "error")

    cursor.execute("SELECT * FROM generos ORDER BY nombre ASC")
    generos = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("admin_generos.html", generos=generos)


@app.route("/admin/genero/borrar/<int:genero_id>", methods=["POST"])
@admin_required
def admin_borrar_genero(genero_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM generos WHERE id = %s", (genero_id,))
        conn.commit()
        flash("Género eliminado correctamente.", "success")
    except mysql.connector.Error:
        flash("No se puede eliminar ese género porque puede estar en uso.", "error")

    cursor.close()
    conn.close()
    return redirect(url_for("admin_generos"))


if __name__ == "__main__":
    app.run(debug=True)