import asyncio
from . import spec
from .exceptions import AMQPError


class Channel(object):
    def __init__(self, protocol, channel_id, dispatcher, loop):
        self.channel_id = channel_id

        self.sender = ChannelMethodSender(channel_id, protocol)

        self.handler = ChannelFrameHandler(channel_id, self.sender, loop)
        self.opened = self.handler.opened
        self.closing = self.handler.closing
        self.closed = self.handler.closed
        dispatcher.add_handler(channel_id, self.handler)

    @asyncio.coroutine
    def close(self):
        """
        Close the channel by handshaking with the server.
        This method is a coroutine.
        """
        self.closing.set_result(True)
        self.sender.send_Close(0, 'Channel closed by application', 0, 0)
        yield from self.closed


class ChannelFrameHandler(object):
    def __init__(self, channel_id, sender, loop):
        self.channel_id = channel_id
        self.sender = sender

        self.opened = asyncio.Future(loop=loop)
        self.closing = asyncio.Future(loop=loop)
        self.closed = asyncio.Future(loop=loop)

    def handle(self, frame):
        method_type = type(frame.payload)
        handle_name = method_type.__name__
        if self.closing.done() and method_type not in (spec.ChannelClose, spec.ChannelCloseOK):
            return

        try:
            handler = getattr(self, 'handle_' + handle_name)
        except AttributeError as e:
            raise AMQPError('No handler defined for {} on channel {}'.format(handle_name, self.channel_id)) from e
        else:
            handler(frame)

    def handle_ChannelOpenOK(self, frame):
        self.opened.set_result(True)

    def handle_ChannelClose(self, frame):
        self.closing.set_result(True)
        self.sender.send_CloseOK()

    def handle_ChannelCloseOK(self, frame):
        self.closed.set_result(True)


class ChannelMethodSender(object):
    def __init__(self, channel_id, protocol):
        self.channel_id = channel_id
        self.protocol = protocol

    def send_Close(self, status_code, message, class_id, method_id):
        self.protocol.send_method(self.channel_id, spec.ChannelClose(0, 'Channel closed by application', 0, 0))

    def send_CloseOK(self):
        self.protocol.send_method(self.channel_id, spec.ChannelCloseOK())
