__all__ = [
	'DataReader',
	'decode_synchsafe_int',
	'get_image_size',
	'humanize_bitrate',
	'humanize_duration',
	'humanize_filesize',
	'humanize_sample_rate'
]

import os
import struct
from codecs import BOM_UTF16_BE, BOM_UTF16_LE
from functools import reduce
from io import DEFAULT_BUFFER_SIZE, BytesIO

from attr import attrib, attrs


@attrs(slots=True)
class DataReader:
	data = attrib()

	def __attrs_post_init__(self):
		if not hasattr(self.data, 'read'):
			self.data = BytesIO(self.data)

	def close(self):
		self.data.close()

	def peek(self, size=DEFAULT_BUFFER_SIZE):
		if size > DEFAULT_BUFFER_SIZE:
			size = DEFAULT_BUFFER_SIZE

		peeked = None
		try:
			peeked = self.data.peek(size)[:size]
		except AttributeError:
			pass

		if peeked is None or len(peeked) != size:
			peeked = self.data.read(size)
			self.data.seek(-len(peeked), os.SEEK_CUR)

		return peeked

	def read(self, size=None):
		return self.data.read(size)

	def seek(self, offset, whence=os.SEEK_SET):
		self.data.seek(offset, whence)

	def tell(self):
		return self.data.tell()


def decode_bytestring(b, encoding='iso-8859-1'):
	if not b:
		return ''

	if encoding.startswith('utf-16'):
		if len(b) % 2 != 0 and b[-1:] == b'\x00':
			b = b[:-1]

		if b.startswith((BOM_UTF16_BE, BOM_UTF16_LE)):  # pragma: nobranch
			b = b[2:]

	return b.decode(encoding).rstrip('\x00')


def decode_synchsafe_int(data, per_byte):
	return reduce(lambda value, element: (value << per_byte) + element, data, 0)


def determine_encoding(b):
	first = b[0:1]

	if first == b'\x00':
		encoding = 'iso-8859-1'
	elif first == b'\x01':
		encoding = 'utf-16-be' if b[1:3] == BOM_UTF16_BE else 'utf-16-le'
	elif first == b'\x02':
		encoding = 'utf-16-be'
	elif first == b'\x03':
		encoding = 'utf-8'
	else:
		encoding = 'iso-8859-1'

	return encoding


def get_image_size(data):
	if not isinstance(data, DataReader):  # pragma: nocover
		data = DataReader(data)

	b = data.read(56)
	size = len(b)

	width = height = 0
	if size >= 10 and b[:6] in [b'GIF87a', b'GIF89a']:
		width, height = struct.unpack('<hh', b[6:10])
	elif size >= 24 and b.startswith(b'\x89PNG') and b[12:16] == b'IHDR':
		width, height = struct.unpack('>LL', b[16:24])
	elif size >= 2 and b.startswith(b'\xff\xd8'):
		data.seek(0)

		size = 2
		ftype = 0
		while not 0xc0 <= ftype <= 0xcf or ftype in [0xc4, 0xc8, 0xcc]:
			data.seek(size, os.SEEK_CUR)
			while True:
				b = data.read(1)
				if b != b'\xff':
					break

			ftype = ord(b)
			size = struct.unpack('>H', data.read(2))[0] - 2

		data.seek(1, os.SEEK_CUR)
		height, width = struct.unpack('>HH', data.read(4))
	elif size >= 12 and b.startswith(b'\x00\x00\x00\x0cjP'):
		height, width = struct.unpack('>LL', b[48:])
	else:
		raise ValueError(f"'data' is not a supported image file.")

	return width, height


def humanize_bitrate(bitrate):
	for divisor, symbol in [(1000 ** 1, 'Kbps'), (1, 'bps')]:
		if bitrate >= divisor:
			break

	return f'{round(bitrate / divisor)} {symbol}'


def humanize_duration(duration):
	if duration // 3600:
		hours = int(duration // 3600)
		minutes = int(duration % 3600 // 60)
		seconds = round(duration % 3600 % 60)

		return f'{hours:02d}:{minutes:02d}:{seconds:02d}'
	elif duration // 60:
		minutes = int(duration // 60)
		seconds = round(duration % 60)

		return f'{minutes:02d}:{seconds:02d}'
	else:
		return f'00:{round(duration):02d}'


def humanize_filesize(filesize, *, precision=0):
	for divisor, symbol in [(1024 ** 3, 'GiB'), (1024 ** 2, 'MiB'), (1024 ** 1, 'KiB'), (1, 'B')]:
		if filesize >= divisor:
			break

	return f'{filesize / divisor:.{precision}f} {symbol}'


def humanize_sample_rate(sample_rate):
	for divisor, symbol in [(1000 ** 1, 'KHz'), (1, 'Hz')]:
		if sample_rate >= divisor:
			break

	value = sample_rate / divisor

	return f'{value if value.is_integer() else value:.1f} {symbol}'


def split_encoded(data, encoding):
	try:
		if encoding in ['iso-8859-1', 'utf-8']:
			head, tail = data.split(b'\x00', 1)
		else:
			if len(data) % 2 != 0:
				data += b'\x00'

			head, tail = data.split(b'\x00\x00', 1)

			if len(head) % 2 != 0:
				head, tail = data.split(b'\x00\x00\x00', 1)
				head += b'\x00'
	except ValueError:
		return (data,)

	return head, tail
