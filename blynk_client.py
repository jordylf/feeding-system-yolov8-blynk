"""HTTPS requests never retry actuator commands after an uncertain response."""
from urllib.parse import urlparse

import requests


class BlynkError(RuntimeError):
    pass


def scalar(value):
    if isinstance(value, list):
        if len(value) != 1:
            raise BlynkError('Nilai datastream bukan scalar.')
        return value[0]
    return value


class BlynkClient:
    def __init__(self, token, server='https://blynk.cloud', session=None):
        parsed = urlparse(server)
        if parsed.scheme != 'https' or not parsed.hostname or not (
            parsed.hostname == 'blynk.cloud' or parsed.hostname.endswith('.blynk.cloud')
        ) or parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.username or parsed.port:
            raise ValueError('BLYNK_SERVER harus HTTPS domain blynk.cloud tanpa path/port.')
        self.server = server.rstrip('/')
        self.token = token
        self.session = session or requests.Session()

    def _request(self, endpoint, params):
        try:
            response = self.session.get(
                f'{self.server}/external/api/{endpoint}',
                params={'token': self.token, **params}, timeout=(3, 4), allow_redirects=False,
            )
        except requests.RequestException:
            # requests exceptions can contain the URL including the token.
            raise BlynkError('Blynk tidak terjangkau; hasil perintah mungkin belum diketahui.') from None
        if response.status_code != 200:
            raise BlynkError(f'Blynk HTTP {response.status_code}; cek server, token, dan datastream.')
        if endpoint == 'update':
            return None
        try:
            result = response.json()
        except ValueError:
            raise BlynkError('Respons Blynk bukan JSON yang valid.') from None
        if isinstance(result, dict) and 'error' in result:
            raise BlynkError('Blynk menolak permintaan; cek konfigurasi datastream.')
        return result

    def snapshot(self):
        online = self._request('isHardwareConnected', {})
        if online not in (True, 'true', 1):
            raise BlynkError('ESP32 offline. Jalankan Wokwi atau nyalakan perangkat.')
        pins = ('v0', 'v1', 'v2', 'v4', 'v5', 'v6', 'v7', 'v8')
        data = self._request('get', {pin: '' for pin in pins})
        if not isinstance(data, dict):
            raise BlynkError('Blynk tidak mengembalikan data beberapa pin.')
        if any(pin not in data for pin in ('v0', 'v6', 'v7')):
            raise BlynkError('Datastream kontrol V0/V6/V7 belum tersedia.')
        return {key: scalar(value) for key, value in data.items()}

    def command(self, gesture):
        data = self.snapshot()
        try:
            desired, actual, busy = (int(data[p]) for p in ('v0', 'v6', 'v7'))
        except (TypeError, ValueError):
            raise BlynkError('Status kontrol Blynk tidak valid.') from None
        if desired not in (0, 1) or actual not in (0, 1) or busy not in (0, 1):
            raise BlynkError('Status kontrol Blynk di luar rentang 0/1.')
        if desired != actual:
            raise BlynkError('ESP32 belum mengonfirmasi perubahan ON/OFF.')
        if gesture == 'palm open':
            self._request('update', {'v0': 1 - actual})
            return 'Permintaan ON dikirim' if not actual else 'Permintaan OFF dikirim'
        if gesture == 'finger up':
            if not actual:
                return 'Pakan ditolak: sistem OFF'
            if busy:
                return 'Pakan ditolak: servo sedang bekerja'
            self._request('update', {'v3': 1})
            return 'Permintaan pakan dikirim; lihat V8 untuk hasil ESP32'
        raise ValueError('Gestur tidak didukung.')

    def close(self):
        self.session.close()
