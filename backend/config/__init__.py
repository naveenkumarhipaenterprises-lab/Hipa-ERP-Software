"""
MySQL driver setup.

This PC runs Windows Smart App Control, which blocks the compiled `mysqlclient`
driver. PyMySQL is a pure-Python MySQL driver that Django supports through this
shim: it registers itself as `MySQLdb` and reports a version Django accepts.
"""
import pymysql

pymysql.version_info = (2, 2, 1, "final", 0)
pymysql.install_as_MySQLdb()
