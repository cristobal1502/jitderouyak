# Si no está instalado mysqlclient (compilado), se usa PyMySQL (puro Python) como driver de MySQL.
try:
    import MySQLdb  # noqa: F401
except ImportError:
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass  # sin driver MySQL: usa DB_ENGINE=sqlite o instala requirements.txt
