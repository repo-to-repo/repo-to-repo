import io
import bz2
import gzip
import lzma
import hashlib

class CreateCompressedHashedFiles:
    def __init__(self, file_path: str, content: str):
        self.file_path = file_path
        self.content = content.encode('utf-8')
        self.hashes = {
            "plain": {"md5": hashlib.md5(), "sha1": hashlib.sha1(), "sha256": hashlib.sha256(), "sha512": hashlib.sha512(), "size": 0},
            "gzip": {"md5": hashlib.md5(), "sha1": hashlib.sha1(), "sha256": hashlib.sha256(), "sha512": hashlib.sha512(), "size": 0},
            "bzip2": {"md5": hashlib.md5(), "sha1": hashlib.sha1(), "sha256": hashlib.sha256(), "sha512": hashlib.sha512(), "size": 0},
            "xz": {"md5": hashlib.md5(), "sha1": hashlib.sha1(), "sha256": hashlib.sha256(), "sha512": hashlib.sha512(), "size": 0}
        }
        self.makePlain()
        self.makeGzip()
        self.makeBzip2()
        self.makeXz()

    def update_hashes(self, method, data):
        self.hashes[method]["md5"].update(data)
        self.hashes[method]["sha1"].update(data)
        self.hashes[method]["sha256"].update(data)
        self.hashes[method]["sha512"].update(data)
        self.hashes[method]["size"] = len(data)

    def makePlain(self):
        self.update_hashes("plain", self.content)
        with open(self.file_path, 'wb') as f:
            f.write(self.content)

    def makeGzip(self):
        fileContent = io.BytesIO()
        with gzip.open(fileContent, mode="wb", compresslevel=9) as file_out:
            file_out.write(self.content)
        self.update_hashes("gzip", fileContent.getvalue())
        with open(f"{self.file_path}.gz", 'wb') as f:
            f.write(fileContent.getvalue())

    def makeBzip2(self):
        fileContent = io.BytesIO()
        with bz2.BZ2File(fileContent, mode="wb", compresslevel=9) as file_out:
            file_out.write(self.content)
        self.update_hashes("bzip2", fileContent.getvalue())
        with open(f"{self.file_path}.bz2", 'wb') as f:
            f.write(fileContent.getvalue())

    def makeXz(self):
        fileContent = io.BytesIO()
        with lzma.open(fileContent, mode="wb") as file_out:
            file_out.write(self.content)
        self.update_hashes("xz", fileContent.getvalue())
        with open(f"{self.file_path}.xz", 'wb') as f:
            f.write(fileContent.getvalue())
