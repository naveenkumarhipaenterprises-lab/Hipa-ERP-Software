"""
Retired Production module: migration history only, no models, views or URLs.

It keeps the app label "production" because the database's migration history (and Quality's
first migration) refers to it. Its last migration drops the old production tables.
"""
