
import errno, hashlib, os, tinydb

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

class FileService:
    db_dir = ".browsepy/share/"
    db_path = db_dir + "db.json"
    table_name = "share"

    mkdir_p(db_dir)
    db = tinydb.TinyDB(db_path)
    share_table = db.table(table_name)

    def clear(self):
        self.db.purge_table(self.table_name)
        self.share_table = self.db.table(self.table_name)

    def add_file(self, filepath):
        hash = hashlib.sha256(filepath).hexdigest()
        existing = self.get_file(hash)

        if existing:
            return existing["hash"]

        self.share_table.insert({
            "hash": hash,
            "path": filepath
        })
        return hash

    def get_file(self, hash):
        file = tinydb.Query()
        results = self.share_table.search(file.hash == hash)
        if not results:
            return None
        else:
            return results[0]

    def file_read_generator(self, file):
        file = open(file["path"])
        while True:
            data = file.read(1024)
            if not data:
                break
            yield data
