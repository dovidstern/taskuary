"""Where a report is ALLOWED to be sent.

The builder used to offer six channels from a hardcoded list and a text box labelled "the chat
id it lands in". Neither half is knowable: WhatsApp was offered on a machine that had never
paired a phone, and a Graph chat id or a WhatsApp JID is not something anyone types from memory
- so the mistake surfaced at 6am as a report that quietly went nowhere.

So the roster is computed: a channel appears only when send_out can carry it, replies are on for
it, and a connector of that kind is active; and on each channel only the destinations Taskuary
has actually seen are offered.
"""
import json
import unittest

from taskuary import outbound
from taskuary.store import MemoryStore


def _conn(s, ctype, name=None, active=1, cfg=None):
    return s.save_connector({'Type': ctype, 'Name': name or ctype, 'Active': active,
                             'ConfigJson': json.dumps(cfg or {})}, 't')


def _chat(s, channel, cid, name, sent='2026-08-30 09:00:00'):
    s.add_message({'Channel': channel, 'ConversationId': cid, 'ExternalId': f'{channel}:{cid}:{name}',
                   'FromName': name, 'Direction': 'in', 'Subject': 'hi', 'BodyText': 'hi',
                   'SentAt': sent, 'Status': 'filed'})


class WhichChannelsTests(unittest.TestCase):
    def test_a_channel_with_no_connector_behind_it_is_not_offered(self):
        s = MemoryStore()
        _conn(s, 'telegram')
        self.assertEqual(outbound.send_channels(s), ['telegram'])

    def test_a_mailbox_of_any_kind_is_what_makes_email_sendable(self):
        s = MemoryStore()
        self.assertEqual(outbound.send_channels(s), [])
        _conn(s, 'imap', 'work mail', cfg={'address': 'uri@example.org'})
        self.assertEqual(outbound.send_channels(s), ['email'])

    def test_replies_switched_off_removes_the_channel_from_the_list(self):
        s = MemoryStore()
        _conn(s, 'whatsapp')
        _conn(s, 'telegram')
        s.set_setting('reply_channels', 'telegram', 't')
        self.assertEqual(outbound.send_channels(s), ['telegram'])

    def test_an_inactive_connector_is_not_a_live_channel(self):
        s = MemoryStore()
        _conn(s, 'discord', active=0)
        self.assertEqual(outbound.send_channels(s), [])

    def test_slack_is_never_offered_because_send_out_cannot_carry_it(self):
        """It is a reply channel with no sender in outbound - offering it would be a promise
        the send path breaks."""
        s = MemoryStore()
        _conn(s, 'slack')
        self.assertEqual(outbound.send_channels(s), [])


class WhichDestinationsTests(unittest.TestCase):
    def test_your_own_notify_chat_comes_first_and_says_it_is_you(self):
        s = MemoryStore()
        _conn(s, 'whatsapp', cfg={'notify_chat': '15551230000@s.whatsapp.net'})
        _chat(s, 'whatsapp', 'whatsapp:15559999999@s.whatsapp.net', 'Dana')
        (wa,) = outbound.send_targets(s)
        self.assertEqual(wa['channel'], 'whatsapp')
        self.assertEqual([t['to'] for t in wa['to']],
                         ['15551230000@s.whatsapp.net', '15559999999@s.whatsapp.net'])
        self.assertIn('you', wa['to'][0]['name'])

    def test_the_channel_prefix_is_stripped_so_the_id_is_the_one_the_sender_wants(self):
        """The message row holds 'teams:19:x@thread.v2'; send_teams wants '19:x@thread.v2'."""
        s = MemoryStore()
        _conn(s, 'teams')
        _chat(s, 'teams', 'teams:19:abc@thread.v2', 'Ops standup')
        (teams,) = outbound.send_targets(s)
        self.assertEqual([t['to'] for t in teams['to']], ['19:abc@thread.v2'])
        self.assertEqual(teams['to'][0]['name'], 'Ops standup')

    def test_a_chat_on_a_channel_that_cannot_send_is_not_offered_anywhere(self):
        s = MemoryStore()
        _conn(s, 'telegram')
        _chat(s, 'discord', 'discord:4242', 'a dev channel')
        (tg,) = outbound.send_targets(s)
        self.assertEqual(tg['to'], [])

    def test_a_chat_taskuary_takes_messages_from_is_offered_with_the_name_it_knows(self):
        s = MemoryStore()
        cid = _conn(s, 'telegram')
        s.save_source({'Channel': 'telegram', 'Address': '778899', 'ConnectorId': cid, 'Active': 1}, 't')
        _chat(s, 'telegram', 'telegram:778899', 'Night shift')
        (tg,) = outbound.send_targets(s)
        self.assertEqual([(t['to'], t['name']) for t in tg['to']], [('778899', 'Night shift')])

    def test_email_offers_the_address_book_and_your_own_mailbox(self):
        s = MemoryStore()
        _conn(s, 'imap', 'work mail', cfg={'address': 'uri@example.org'})
        s.add_message({'Channel': 'email', 'ExternalId': 'imap:1', 'FromEmail': 'dana@vendor.com',
                       'FromName': 'Dana Reed', 'Subject': 'invoice', 'BodyText': 'x',
                       'SentAt': '2026-08-30 08:00:00', 'Status': 'filed'})
        (mail,) = outbound.send_targets(s)
        self.assertEqual([t['to'] for t in mail['to']], ['uri@example.org', 'dana@vendor.com'])
        self.assertEqual(mail['to'][1]['name'], 'Dana Reed')

    def test_every_destination_carries_something_to_read(self):
        """A picker row with an empty name would show as a blank line."""
        s = MemoryStore()
        _conn(s, 'whatsapp')
        _chat(s, 'whatsapp', 'whatsapp:15551110000@s.whatsapp.net', None)
        (wa,) = outbound.send_targets(s)
        self.assertEqual(wa['to'][0]['name'], '15551110000@s.whatsapp.net')

    def test_what_is_offered_is_exactly_what_send_out_would_accept(self):
        s = MemoryStore()
        _conn(s, 'telegram', cfg={'notify_chat': '4242'})
        for entry in outbound.send_targets(s):
            self.assertTrue(outbound.can_reply(s, entry['channel']))
            self.assertIn(entry['channel'], outbound.REPORTABLE)


if __name__ == '__main__':
    unittest.main()
