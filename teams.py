import file_database
import users
teams_database_path = 'teams_database.txt'

file_database.initialize_file_database(teams_database_path)

class AlreadyExists(Exception):
    pass

class NotFound(Exception):
    pass

class UsernameNotFound(Exception):
    pass

def remove_team_member(team_name, team_member):
    def transform_database(database_contents):
        if not _team_already_exists(team_name):
            raise NotFound
        database_contents[team_name]['usernames'].remove(team_member)
        return database_contents
    file_database.transform_file(teams_database_path, transform_database)

def add_team_member(team_name, team_member):
    def transform_database(database_contents):
        if not _team_already_exists(team_name):
            raise NotFound
        if not users.username_exists(team_member):
            raise users.NotFound
        database_contents[team_name]['usernames'].add(team_member)
        return database_contents
    file_database.transform_file(teams_database_path, transform_database)

def create_team(team_name, username):
    def transform_database(database_contents):
        if _team_already_exists(team_name):
            raise AlreadyExists
        if not users.username_exists(username):
            raise users.NotFound
        database_contents[team_name] = {'usernames': set(), 'creator': username}
        return database_contents
    file_database.transform_file(teams_database_path, transform_database)

def get_team(team_name):
    teams = file_database.get_database_contents(teams_database_path)
    if team_name not in teams:
        raise NotFound
    return teams[team_name]

def _team_already_exists(team_name):
    return team_name in file_database.get_database_contents(teams_database_path)

