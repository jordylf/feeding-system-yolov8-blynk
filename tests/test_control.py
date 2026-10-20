import unittest
from unittest.mock import Mock

import requests

from blynk_client import BlynkClient, BlynkError
from gesture_control import GestureGate


class GestureTests(unittest.TestCase):
    def test_held_hand_fires_once_and_requires_release(self):
        gate = GestureGate()
        self.assertIsNone(gate.update('palm-open', 0))
        self.assertEqual(gate.update('palm open', 1), 'palm open')
        self.assertIsNone(gate.update('palm open', 30))
        self.assertIsNone(gate.update('finger up', 31))
        gate.update(None, 32)
        gate.update(None, 32.7)
        gate.update('finger up', 33)
        self.assertEqual(gate.update('finger up', 34), 'finger up')

    def test_switching_label_resets_hold(self):
        gate = GestureGate()
        gate.update('palm open', 0)
        self.assertIsNone(gate.update('finger up', 0.9))
        self.assertIsNone(gate.update('finger up', 1.1))
        self.assertEqual(gate.update('finger up', 2), 'finger up')

    def test_brief_missed_detection_does_not_rearm(self):
        gate = GestureGate()
        gate.update('finger up', 0)
        gate.update('finger up', 1)
        gate.update(None, 10)
        self.assertIsNone(gate.update('finger up', 10.1))
        self.assertIsNone(gate.update('finger up', 12))

    def test_ambiguous_detections_do_not_count_as_release(self):
        gate = GestureGate()
        gate.update('palm open', 0)
        gate.update('palm open', 1)
        gate.update('ambiguous', 10)
        gate.update('ambiguous', 20)
        self.assertIsNone(gate.update('palm open', 30))


class BlynkTests(unittest.TestCase):
    def client(self, active=0, busy=0, desired=None):
        session = Mock()
        response = Mock(status_code=200)
        response.json.side_effect = [True, {
            'v0': active if desired is None else desired, 'v6': [active], 'v7': busy,
        }]
        session.get.return_value = response
        return BlynkClient('test-token', session=session), session

    def test_manual_off_never_writes(self):
        client, session = self.client()
        self.assertIn('OFF', client.command('finger up'))
        self.assertEqual(session.get.call_count, 2)

    def test_busy_never_writes(self):
        client, session = self.client(1, 1)
        self.assertIn('servo', client.command('finger up'))
        self.assertEqual(session.get.call_count, 2)

    def test_manual_on_sends_v3_once(self):
        client, session = self.client(1)
        client.command('finger up')
        self.assertEqual(session.get.call_count, 3)
        self.assertEqual(session.get.call_args.kwargs['params']['v3'], 1)

    def test_toggle_uses_actual_state(self):
        client, session = self.client(1)
        client.command('palm open')
        self.assertEqual(session.get.call_args.kwargs['params']['v0'], 0)

    def test_pending_state_is_rejected(self):
        client, session = self.client(0, desired=1)
        with self.assertRaises(BlynkError):
            client.command('palm open')
        self.assertEqual(session.get.call_count, 2)

    def test_offline_rejects_command(self):
        client, session = self.client()
        session.get.return_value.json.side_effect = [False]
        with self.assertRaises(BlynkError):
            client.command('finger up')
        self.assertEqual(session.get.call_count, 1)

    def test_timeout_hides_token_and_is_not_retried(self):
        client, session = self.client()
        session.get.side_effect = requests.Timeout('URL contains test-token')
        with self.assertRaises(BlynkError) as error:
            client.command('finger up')
        self.assertNotIn('test-token', str(error.exception))
        self.assertEqual(session.get.call_count, 1)

    def test_http_error_does_not_claim_success(self):
        client, session = self.client()
        session.get.return_value.status_code = 400
        with self.assertRaises(BlynkError):
            client.command('palm open')

    def test_server_cannot_leak_token_to_arbitrary_host(self):
        for server in ['http://blynk.cloud', 'https://blynk.cloud.evil.test', 'https://evil.test']:
            with self.assertRaises(ValueError):
                BlynkClient('secret', server)


if __name__ == '__main__':
    unittest.main()
