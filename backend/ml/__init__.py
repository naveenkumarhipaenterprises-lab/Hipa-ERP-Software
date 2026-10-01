"""
Analytics engine. Everything here works only on real records from the database.
When there isn't enough history, functions return an InsufficientData result instead
of a number, and the API passes that state to the frontend.
"""
