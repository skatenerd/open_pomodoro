import hashlib
import file_database

accounts_database_path = 'accounts_database.txt'
salt = "abcdabcdabcdabcdabcdabcdabcdabcd"

class NotFound(Exception):
    pass

class AlreadyExists(Exception):
    pass

file_database.initialize_file_database(accounts_database_path)

def username_exists(username):
    return username in file_database.get_database_contents(accounts_database_path)

def valid_login(username, password):
    accounts = file_database.get_database_contents(accounts_database_path)
    return accounts.get(username) == hash_password(password)

def set_password(username, password):
    def transform_database(database):
        if username_exists(username):
            raise AlreadyExists
        database[username] = hash_password(password)
        return database
    file_database.transform_file(accounts_database_path, transform_database)

def hash_password(password):
    return hashlib.sha512(password + salt).hexdigest()
