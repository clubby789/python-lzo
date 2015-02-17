
import struct
import io
import __builtin__
from _lzo import *

__all__ = ["LzoFile","open"]


READ, WRITE = 1, 2

ADLER32_INIT_VALUE = 1
CRC32_INIT_VALUE = 0


LZOP_VERSION = 0x1030

MAX_BLOCK_SIZE = (64*1024l*1024L)

F_ADLER32_D     = 0x00000001L
F_ADLER32_C     = 0x00000002L
F_STDIN         = 0x00000004L
F_STDOUT        = 0x00000008L
F_NAME_DEFAULT  = 0x00000010L
F_DOSISH        = 0x00000020L
F_H_EXTRA_FIELD = 0x00000040L
F_H_GMTDIFF     = 0x00000080L
F_CRC32_D       = 0x00000100L
F_CRC32_C       = 0x00000200L
F_MULTIPART     = 0x00000400L
F_H_FILTER      = 0x00000800L
F_H_CRC32       = 0x00001000L
F_H_PATH        = 0x00002000L
F_MASK          = 0x00003FFFL


class LzoFile(io.BufferedIOBase):

    def __init__(self, filename=None, mode=None,
                 compresslevel=9, fileobj=None, mtime=None):
        """Constructor for the GzipFile class.

        At least one of fileobj and filename must be given a
        non-trivial value.

        The new class instance is based on fileobj, which can be a regular
        file, a StringIO object, or any other object which simulates a file.
        It defaults to None, in which case filename is opened to provide
        a file object.

        When fileobj is not None, the filename argument is only used to be
        included in the gzip file header, which may includes the original
        filename of the uncompressed file.  It defaults to the filename of
        fileobj, if discernible; otherwise, it defaults to the empty string,
        and in this case the original filename is not included in the header.


        """

        # guarantee the file is opened in binary mode on platforms
        # that care about that sort of thing
        if mode:
            if 'b' not in mode:  mode += 'b'
        else:
            mode = 'rb'

        if fileobj is None:
            fileobj = __builtin__.open(filename, mode)
        if filename is None:
            if hasattr(fileobj, 'name'): filename = fileobj.name
            else: filename = ''
        if mode is None:
            if hasattr(fileobj, 'mode'): mode = fileobj.mode
            else: mode = 'rb'

        if mode[0:1] == 'r':
            self.mode = READ

        elif mode[0:1] == 'w' or mode[0:1] == 'a':
            self.mode = WRITE

        else:
            raise IOError, "Mode " + mode + " not supported"

        self.fileobj = fileobj
        self.offset = 0

    def _read_magic(self):
        MAGIC = b"\x89\x4C\x5A\x4F\x00\x0D\x0A\x1A\x0A"
        magic = self.fileobj.read(len(MAGIC))

        if magic == MAGIC:
            return True
        else:
            raise IOError, 'Wrong lzo signature'

    def _read_header(self):
        self.adler32 = ADLER32_INIT_VALUE
        self.crc32 = CRC32_INIT_VALUE

        print 'debug'

        self.version = self._read16_c()
        self.libver = self._read16_c()

        if self.version > 0x0940:
            self.ver_need_ext = self._read16_c()
            if self.ver_need_ext > LZOP_VERSION:
                raise IOError, 'Need liblzo version higher than %s' %(hex(self.ver_need_ext))
            elif self.ver_need_ext < 0x0900:
                raise IOError, '3'

        self.method = self._read8_c()
        assert(self.method in [1,2,3])
        

        if self.version >= 0x0940:
            self.level = self._read8_c()

        self.flags = self._read32_c()

        if self.flags & F_H_CRC32:
            raise _lzo.error, 'CRC32 not implemented in minilzo'

        if self.flags & F_H_FILTER:
            self.ffilter = self._read32()

        self.mode = self._read32_c()
        self.mtime_low = self._read32_c()
        if self.version >= 0x0940:
            self.mtime_high = self._read32_c()

        l = self._read8_c()
        self.name = self._read_c(l)

        checksum = self.crc32 if self.flags & F_H_CRC32 else self.adler32

        self.header_checksum = self._read32_c()
        assert checksum == self.header_checksum

        if self.flags & F_H_EXTRA_FIELD:
            l = self._read32_c()
            self.extra = self._read_c(l)
            checksum = self.crc32 if self.flags & F_H_CRC32 else self.adler32
            assert checksum == self._read32_c()

    def _read_block(self):
        dst_len = self._read32()
        if dst_len == 0:
            return None

        if dst_len > MAX_BLOCK_SIZE:
            raise _lzo.error, 'uncompressed larger than max block size'

        src_len = self._read32()

        if self.flags & F_ADLER32_D:
            d_adler32 = self._read32()

        if self.flags & F_CRC32_D:
            d_crc32 = self._read32()

        if self.flags & F_ADLER32_C:
            if src_len < dst_len:
                c_adler32 = self._read32()
            else:
                c_adler32 = d_adler32

        if self.flags & F_CRC32_C:
            if src_len < dst_len:
                c_crc32 = self._read32()
            else:
                c_crc32 = d_crc32

        block = self.fileobj.read(src_len)
        uncompressed = decompress_block(block, dst_len)

        print src_len, dst_len
        print len(block), len(uncompressed)
        return uncompressed

    def _read_c(self, n):
        bytes = self.fileobj.read(n)
        #print hex(self.adler32)
        self.adler32 = lzo_adler32(self.adler32, bytes)

        #if lzo_crc32:
        #    self.crc32 = lzo_crc32(self.crc32, bytes)

        return bytes

    def _read32_c(self):
        return struct.unpack(">I", self._read_c(4))[0]

    def _read16_c(self):
        return struct.unpack(">H", self._read_c(2))[0]
        
    def _read8_c(self):
        return ord(self._read_c(1))

    def _read32(self):
        return struct.unpack(">I", self.fileobj.read(4))[0]

    def _read16(self):
        return struct.unpack(">H", self.fileobj.read(2))[0]
        
    def _read8(self):
        return ord(self.fileobj.read(1))


    def read(self):
        self._read_magic()
        self._read_header()


f = LzoFile(filename = 'test.lzo')
print 'magic', f._read_magic()
f._read_header()
f._read_block()