"""Private content-addressed media, separate from the content SQLite database."""
import hashlib
import os
from pathlib import Path
import re
import tempfile


class MediaStore:
    def __init__(self, root):
        self.root = Path(root)

    def path(self, key):
        if not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{64}', key):
            raise ValueError('Invalid media storage key')
        return self.root / key[:2] / key

    def put(self, data):
        key = hashlib.sha256(data).hexdigest()
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            self.verify(key)
            return key
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
                temporary = Path(output.name)
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            self.verify_file(temporary, key)
            os.replace(temporary, path)
            # Persist the directory entry before committing its database reference.
            for directory in (path.parent, self.root, self.root.parent):
                fd = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return key

    def get(self, key):
        try:
            return self.path(key).read_bytes()
        except FileNotFoundError:
            return None

    @staticmethod
    def verify_file(path, key):
        path = Path(path)
        if path.is_symlink():
            raise ValueError('Media object must not be a symbolic link')
        digest = hashlib.sha256()
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != key:
            raise ValueError(f'Media checksum mismatch: {key}')

    def verify(self, key):
        self.verify_file(self.path(key), key)
