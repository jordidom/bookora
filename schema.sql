CREATE DATABASE IF NOT EXISTS bookora CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bookora;

DROP TABLE IF EXISTS libros;
DROP TABLE IF EXISTS generos;
DROP TABLE IF EXISTS admins;

CREATE TABLE generos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL
);

CREATE TABLE libros (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    autor VARCHAR(150) NOT NULL,
    genero_id INT,
    anio_publicacion INT,
    idioma VARCHAR(50),
    sinopsis TEXT,
    editorial VARCHAR(150),
    paginas INT,
    portada VARCHAR(255),
    archivo_pdf VARCHAR(255),
    archivo_epub VARCHAR(255),
    is_featured TINYINT(1) DEFAULT 0,
    downloads_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (genero_id) REFERENCES generos(id) ON DELETE SET NULL
);

INSERT INTO generos (nombre) VALUES
('Novela'),
('Fantasía'),
('Ciencia ficción'),
('Terror'),
('Romance'),
('Historia'),
('Aventura'),
('Misterio');

INSERT INTO admins (username, password)
VALUES ('admin', 'scrypt:32768:8:1$r3mJoc9RBfjDHH7l$017306231661c727a30b5b3592f7682b7337f7660f1ed2039ce98244c7ebf0f85e4f46f63b9c98c23c6192ef19e57fa7597bc97bd5a13eeb391765965ab4c4b3');