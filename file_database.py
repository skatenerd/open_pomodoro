import tempfile
import gevent.lock
import os
import pickle

db_write_lock = gevent.lock.Semaphore()

def initialize_file_database(path):
    if not os.path.isfile(path):
        with open(path, 'w') as f:
            pickle.dump({}, f)

def get_database_contents(path):
    with open(path, 'r') as f:
        contents = pickle.load(f)
    return contents

def write_database_contents(contents, path):
    with tempfile.NamedTemporaryFile(delete=False) as out_tmp:
        pickle.dump(contents, out_tmp)
        os.rename(out_tmp.name, path)

def transform_file(path, transformation):
    try:
        db_write_lock.acquire()
        contents = get_database_contents(path)
        new_contents = transformation(contents)
        write_database_contents(new_contents, path)
    finally:
        db_write_lock.release()
