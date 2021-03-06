#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import ctypes
import hashlib
import ctypes.util

__title__ = 'worldcoin'
__version__ = '1.0.2'
__author__ = '@c0ding'
__repo__ = 'https://github.com/c0ding/worldcoin-api'
__license__ = 'Apache v2.0 License'

"""
This part of the code is where the magic happens.
Joric/bitcoin-dev, june 2012, public domain
modified by c0ding, 2014
"""

ssl = ctypes.cdll.LoadLibrary (ctypes.util.find_library ('ssl') or 'libeay32')


def check_result (val, func, args):
	if val == 0: raise ValueError 
	else: return ctypes.c_void_p (val)


ssl.EC_KEY_new_by_curve_name.restype = ctypes.c_void_p
ssl.EC_KEY_new_by_curve_name.errcheck = check_result

class KEY:
	def __init__(self):
		NID_secp256k1 = 714
		self.k = ssl.EC_KEY_new_by_curve_name(NID_secp256k1)
		self.compressed = False
		self.POINT_CONVERSION_COMPRESSED = 2
		self.POINT_CONVERSION_UNCOMPRESSED = 4

		
	def __del__(self):
		if ssl:
			ssl.EC_KEY_free(self.k)
		self.k = None

		
	def generate(self, secret=None):
		if secret:
			self.prikey = secret
			priv_key = ssl.BN_bin2bn(secret, 32, ssl.BN_new())
			group = ssl.EC_KEY_get0_group(self.k)
			pub_key = ssl.EC_POINT_new(group)
			ctx = ssl.BN_CTX_new()
			ssl.EC_POINT_mul(group, pub_key, priv_key, None, None, ctx)
			ssl.EC_KEY_set_private_key(self.k, priv_key)
			ssl.EC_KEY_set_public_key(self.k, pub_key)
			ssl.EC_POINT_free(pub_key)
			ssl.BN_CTX_free(ctx)
			return self.k
		else:
			return ssl.EC_KEY_generate_key(self.k)


	def get_pubkey(self):
		size = ssl.i2o_ECPublicKey(self.k, 0)
		mb = ctypes.create_string_buffer(size)
		ssl.i2o_ECPublicKey(self.k, ctypes.byref(ctypes.pointer(mb)))
		return mb.raw

		
	def get_secret(self):
		bn = ssl.EC_KEY_get0_private_key(self.k);
		_bytes = (ssl.BN_num_bits(bn) + 7) / 8
		mb = ctypes.create_string_buffer(_bytes)
		n = ssl.BN_bn2bin(bn, mb);
		return mb.raw.rjust(32, chr(0))

		
	def set_compressed(self, compressed):
		self.compressed = compressed
		if compressed:
			form = self.POINT_CONVERSION_COMPRESSED
		else:
			form = self.POINT_CONVERSION_UNCOMPRESSED
		ssl.EC_KEY_set_conv_form(self.k, form)


def dhash(s):
	return hashlib.sha256(hashlib.sha256(s).digest()).digest()

	
def rhash(s):
	h1 = hashlib.new('ripemd160')
	h1.update(hashlib.sha256(s).digest())
	return h1.digest()


b58_digits = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


def base58_encode(n):
	l = []
	while n > 0:
		n, r = divmod(n, 58)
		l.insert(0,(b58_digits[r]))
	return ''.join(l)


def base58_decode(s):
	n = 0
	for ch in s:
		n *= 58
		digit = b58_digits.index(ch)
		n += digit
	return n


def base58_encode_padded(s):
	res = base58_encode(int('0x' + s.encode('hex'), 16))
	pad = 0
	for c in s:
		if c == chr(0):
			pad += 1
		else:
			break
	return b58_digits[0] * pad + res


def base58_decode_padded(s):
	pad = 0
	for c in s:
		if c == b58_digits[0]:
			pad += 1
		else:
			break
	h = '%x' % base58_decode(s)
	if len(h) % 2:
		h = '0' + h
	res = h.decode('hex')
	return chr(0) * pad + res


def base58_check_encode(s, version=0):
	vs = chr(version) + s
	check = dhash(vs)[:4]
	return base58_encode_padded(vs + check)


def base58_check_decode(s, version=0):
	k = base58_decode_padded(s)
	v0, data, check0 = k[0], k[1:-4], k[-4:]
	check1 = dhash(v0 + data)[:4]
	if check0 != check1:
		raise BaseException('checksum error')
	if version != ord(v0):
		raise BaseException('version mismatch')
	return data


def gen_eckey(passphrase=None, secret=None, pkey=None, compressed=False, rounds=1, version=0):
	k = KEY()
	if passphrase:
		secret = passphrase.encode('utf8')
		for i in xrange(rounds):
			secret = hashlib.sha256(secret).digest()
	if pkey:
		secret = base58_check_decode(pkey, 128+version)
		compressed = len(secret) == 33
		secret = secret[0:32]
	k.generate(secret)
	k.set_compressed(compressed)
	return k


def get_addr(k,version=0):
	pubkey = k.get_pubkey()
	secret = k.get_secret()
	hash160 = rhash(pubkey)
	addr = base58_check_encode(hash160,version)
	payload = secret
	if k.compressed:
		payload = secret + chr(1)
	pkey = base58_check_encode(payload, 128+version)
	return json.dumps({'address': addr, 'private_key': pkey}, sort_keys=True)


def reencode(pkey,version=0):
	payload = base58_check_decode(pkey,128+version)
	secret = payload[:-1]
	payload = secret + chr(1)
	pkey = base58_check_encode(payload, 128+version)
	print get_addr(gen_eckey(pkey))


OFFICIAL_BLOCKEXPLORER = 'http://www.worldcoinexplorer.com/api/'
CRYPTOCOIN_API = 'http://api.cryptocoincharts.info/tradingPair/'


def blockexplorer(*suffix):
	"""
	Returns the entrypoint URL for the Worldcoin block API.
	All data provided by the official Worldcoin Blockexplorer.
	http://www.worldcoinexplorer.com
	"""

	return OFFICIAL_BLOCKEXPLORER + '/'.join(suffix)


def exchange(*suffix):
	"""
	Returns the entrypoint URL for the Worldcoin price API.
	All data provided by CryptoCoin.
	http://www.cryptocoincharts.info
	"""

	return CRYPTOCOIN_API + '/'.join(suffix)
