import unittest
import os
import asyncio
from unittest.mock import patch

from electrum_aionostr.relay import Manager
from electrum_aionostr.key import PrivateKey
from electrum_aionostr.event import Event

def get_random_dummy_event() -> Event:
    privkey = PrivateKey(os.urandom(32))
    event = Event(
        pubkey=privkey.public_key.hex(),
        content="test"
    )
    event.sign(privkey.hex())
    return event

class TestManager(unittest.IsolatedAsyncioTestCase):


    async def test_monitor_queues_event_deduplication(self):
        """
        Tests if the events returned by multiple relays are
        properly deduplicated.
        """
        output_queue = asyncio.Queue()  # this is what the consumer of the subscription will receive
        input_queues = [asyncio.Queue() for _ in range(10)]  # these are the relays
        dummy_events = [get_random_dummy_event() for _ in range(20)]

        for queue in input_queues:
            for dummy_event in dummy_events:
                queue.put_nowait(dummy_event)
            queue.put_nowait(None)

        # Create a patched version of Queue.put that adds a delay to force context
        # switching as it happens with regular usage of monitor_queues
        original_put = asyncio.Queue.put
        async def slow_put(self, item):
            await asyncio.sleep(0.01)
            await original_put(self, item)

        with patch('asyncio.Queue.put', slow_put):
            monitoring_task = asyncio.create_task(Manager.monitor_queues(
                input_queues,
                output_queue,
                set(),
            ))
            # check if the output queue returns some events twice
            event_ids = set()
            while True:
                event = await asyncio.wait_for(output_queue.get(), timeout=10)
                if event is None:
                    break
                assert event.id not in event_ids
                event_ids.add(event.id)

        monitoring_task.cancel()
