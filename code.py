import board
import displayio
import struct


def read_blockstream(f):
    while True:
        size = f.read(1)[0]
        if size == 0:
            break
        for i in range(size):
            yield f.read(1)[0]


class EndOfData(Exception):
    pass


class LZWDict:
    def __init__(self, code_size):
        self.code_size = code_size
        self.clear_code = 1 << code_size
        self.end_code = self.clear_code + 1
        self.codes = []
        self.clear()

    def clear(self):
        self.last = b''
        self.code_len = self.code_size + 1
        self.codes = []

    def decode(self, code):
        if code == self.clear_code:
            self.clear()
            return b''
        elif code == self.end_code:
            raise EndOfData()
        elif code < self.clear_code:
            value = bytes([code])
        elif code <= len(self.codes) + self.end_code:
            value = self.codes[code - self.end_code - 1]
        else:
            value = self.last + self.last[0:1]
        if self.last:
            self.codes.append(self.last + value[0:1])
        if (len(self.codes) + self.end_code + 1 >= 1 << self.code_len and
            self.code_len < 12):
                self.code_len += 1
        self.last = value
        return value


def lzw_decode(data, code_size):
    dictionary = LZWDict(code_size)
    bit = 0
    byte = next(data)
    try:
        while True:
            code = 0
            for i in range(dictionary.code_len):
                code |= ((byte >> bit) & 0x01) << i
                bit += 1
                if bit >= 8:
                    bit = 0
                    byte = next(data)
            yield dictionary.decode(code)
    except EndOfData:
        while True:
            next(data)


class Extension:
    def __init__(self,f):
        self.extension_type = f.read(1)[0]
        # 0x01 = label, 0xfe = comment
        self.data = bytes(read_blockstream(f))


class Frame:
    def __init__(self, f, bitmap, palette, colors):
        self.bitmap_class = bitmap
        self.palette_class = palette
        self.x, self.y, self.w, self.h, flags = (
            struct.unpack('<HHHHB', f.read(9)))
        self.palette_flag = (flags & 0x80) != 0
        self.interlace_flag = (flags & 0x40) != 0
        self.sort_flag = (flags & 0x20) != 0
        self.palette_size = 1 << ((flags & 0x07) + 1)
        if self.palette_flag:
            self.read_palette(f)
            colors = self.palette_size
        self.min_code_sz = f.read(1)[0]
        self.bitmap = self.bitmap_class(self.w, self.h, colors)
        x = 0
        y = 0
        for decoded in lzw_decode(read_blockstream(f), self.min_code_sz):
            for byte in decoded:
                self.bitmap[x, y] = byte
                x += 1
                if (x >= self.w):
                    x = 0
                    y += 1

    def read_palette(self, f):
        self.palette = self.palette_class(self.palette_size)
        for i in range(self.palette_size):
            self.palette[i] = f.read(3)


class GIFImage:
    def __init__(self, f, bitmap, palette):
        self.bitmap_class = bitmap
        self.palette_class = palette
        self.read_header(f)
        if self.palette_flag:
            self.read_palette(f)
        self.frames = []
        self.extensions = []
        while True:
            block_type = f.read(1)[0]
            if block_type == 0x3b:
                break
            elif block_type == 0x2c:
                self.frames.append(
                    Frame(f, self.bitmap_class, self.palette_class,
                          self.palette_size))
                # XXX only read the first frame for now
                break
            elif block_type == 0x21:
                self.extensions.append(Extension(f))
            else:
                raise ValueError('Bad block {0:2x}'.format(block_type))

    def read_palette(self, f):
        self.palette = self.palette_class(self.palette_size)
        for i in range(self.palette_size):
            self.palette[i] = f.read(3)

    def read_header(self, f):
        header = f.read(6)
        if header not in {b'GIF87a', b'GIF89a'}:
            raise ValueError("Not GIF file")
        self.w, self.h, flags, self.background, self.aspect = (
            struct.unpack('<HHBBB', f.read(7)))
        self.palette_flag = (flags & 0x80) != 0
        self.sort_flag = (flags & 0x08) != 0
        self.color_bits = ((flags & 0x70) >> 4) + 1
        self.palette_size = 1 << ((flags & 0x07) + 1)


display = board.DISPLAY
group = displayio.Group()
display.show(group)
with open("ball.gif", 'rb') as f:
    gif = GIFImage(f, bitmap=displayio.Bitmap, palette=displayio.Palette)
grid = displayio.TileGrid(gif.frames[0].bitmap, pixel_shader=gif.palette)
group.append(grid)

while True:
    pass
