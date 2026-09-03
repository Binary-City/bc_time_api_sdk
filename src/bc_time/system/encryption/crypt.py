from base64 import b64decode as base64_decode, b64encode as base64_encode
from logging import getLogger
from secrets import choice as secrets_choice
from string import ascii_letters, digits
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

logger = getLogger('bc_time')

class Crypt:
    # Contants
    IV_START_VALUES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'] # a = 1, b = 2..., A = 9, B = 10..., and etc.
    KEY_LENGTH = 32 # The key length BC Time issues; AES itself also accepts 16 or 24.
    VALID_KEY_LENGTHS = (16, 24, 32)
    IV_LENGTH = 16

    # Public
    key = None
    data = None

    def __init__(self, key=None, data=None) -> None:
        self.key = key
        self.data = data

    def encrypt(self) -> str|None:
        if not self.__validate_data():
            return None
        key = self.__get_validated_key()
        iv, iv_start, iv_end = self.__get_iv_and_start_and_end()
        padder = padding.PKCS7(128).padder()
        data_to_encrypt = padder.update(str.encode(self.data)) + padder.finalize()
        iv = str.encode(iv)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(data_to_encrypt) + encryptor.finalize()
        encrypted_data = str(base64_encode(encrypted_data), 'utf-8')
        encrypted_data, equal_signs_count = self.__strip_equal_signs(encrypted_data)
        encrypted_data = iv_start + encrypted_data + iv_end + '='*equal_signs_count # This might result in no equal signs appended.
        return encrypted_data

    def decrypt(self) -> str|None:
        if not self.__validate_data():
            return None
        key = self.__get_validated_key()
        iv, encrypted_data = self.__extract_iv()
        if iv is None or encrypted_data is None:
            return None
        try:
            encrypted_data = base64_decode(encrypted_data)
            iv = str.encode(iv)
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            decrypted_padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
            unpadder = padding.PKCS7(128).unpadder()
            decrypted_data = unpadder.update(decrypted_padded_data) + unpadder.finalize()
            return str(decrypted_data, 'utf-8')
        except ValueError as exception:
            # Covers invalid base64, block-size mismatches, invalid padding and non-UTF-8 plaintext -
            # typically an incorrect crypt_key, or data that was corrupted or tampered with in transit.
            logger.warning("Could not decrypt data - the crypt_key is likely incorrect, or the data was corrupted or tampered with: %s", exception)
            return None

    def __get_validated_key(self) -> bytes:
        key = str.encode(self.key)
        if len(key) not in self.VALID_KEY_LENGTHS:
            raise ValueError(f"crypt_key must be {', '.join(str(length) for length in self.VALID_KEY_LENGTHS)} bytes long; got {len(key)} bytes. Verify the crypt_key issued to you by BC Time.")
        return key

    def __extract_iv_start_length(self) -> tuple[int|None, str|None]:
        first_char = self.data[:1]
        if first_char not in self.IV_START_VALUES:
            return None, None
        encrypted_data = self.data[1:]
        iv_start_length = self.IV_START_VALUES.index(first_char) + 1
        return iv_start_length, encrypted_data

    def __extract_iv(self) -> tuple[str, str]:
        iv_start_length, encrypted_data = self.__extract_iv_start_length()
        if iv_start_length is None or encrypted_data is None:
            return None, None
        iv_end_length = self.IV_LENGTH - iv_start_length
        encrypted_data, equal_signs_count = self.__strip_equal_signs(encrypted_data)
        iv = encrypted_data[:iv_start_length]
        encrypted_data = encrypted_data[iv_start_length:]
        if iv_end_length > 0:
            iv += encrypted_data[iv_end_length*-1:]
        encrypted_data_length = len(encrypted_data)
        encrypted_data = encrypted_data[:encrypted_data_length - iv_end_length]
        encrypted_data += '='*equal_signs_count # This might result in no equal signs appended.
        if len(iv) != self.IV_LENGTH:
            return None, None
        return iv, encrypted_data

    def __strip_equal_signs(self, encrypted_data: str) -> tuple[str, int]:
        stripped_data = encrypted_data.rstrip('=')
        return stripped_data, len(encrypted_data) - len(stripped_data)

    def __validate_data(self) -> bool:
        return self.key is not None and self.data is not None

    def __get_iv_and_start_and_end(self) -> tuple[str, str, str]:
        iv = self.__get_random_iv()
        start_length = self.__get_random_iv_start_length()
        start = self.IV_START_VALUES[start_length - 1] + iv[:start_length]
        end = iv[start_length:]
        return iv, start, end

    def __get_random_iv(self) -> str:
        return ''.join(secrets_choice(ascii_letters + digits) for _ in range(self.IV_LENGTH))

    def __get_random_iv_start_length(self) -> int:
        start_value = secrets_choice(self.IV_START_VALUES)
        return self.IV_START_VALUES.index(start_value) + 1