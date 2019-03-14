import can
from cantools import database
from cantools.database.can import Message
import time
from datetime import datetime


class MessageInfor(object):
    def __init__(self, can_msg, decoded_msg, db_msg):
        self.can_msg = can_msg
        self.decoded_msg = decoded_msg
        self.db_msg = db_msg

class Device(can.Listener):
    """
    A device ref to a can bus, which provide interface to get signals's value easily.
    """
    def __init__(self, data_base, bus_type, channel, bit_rate, encoding="cp1252", frame_id_mask=None, strict = 0):
        self._dbase = database.load_file(data_base,
                                         encoding=encoding,
                                         frame_id_mask=frame_id_mask,
                                         strict=strict)
        self._filter = ''
        self._compiled_filter = None
        self._formatted_messages = {}
        self._message_by_name = {}
        self._message_by_id = {}
        self._send_message_by_name = {}


        self._bus = self.create_bus(bus_type, channel, bit_rate)
        self._notifier = can.Notifier(self._bus, [self])

    def create_bus(self, bus_type, channel, bit_rate):
        kwargs = {}

        if bit_rate is not None:
            kwargs['bitrate'] = int(bit_rate)

        try:
            return can.Bus(bustype=bus_type,
                           channel=channel,
                           **kwargs)
        except:
            raise Exception(
                "Failed to create CAN bus with bustype='{}' and "
                "channel='{}'.".format(bus_type,
                                       channel))

    def on_message_received(self, msg):
        try:
            message = self._dbase.decode_message(msg.arbitration_id, msg.data)
        except KeyError:
            return
        if message:
            msg_ = self._dbase.get_message_by_frame_id(msg.arbitration_id)
            msg_obj = MessageInfor(msg, message, msg_)
            self._message_by_name[msg_.name] = msg_obj
            self._message_by_id[msg.arbitration_id] = msg_obj

    def is_msg_alive(self, message_name, timeout=5):
        """
        check whether a message is alive.
        :param message_name: message name in database.
        :param timeout: if cycle_time in database is not 0, the compared timeout value is: cycle_time*timeout;
               else the compared timeout value is: timeout(seconds).
        :return:
        """
        try:
            msg = self._message_by_name[message_name]

        except KeyError:
            return None
        current_timestamp = datetime.timestamp(datetime.now())
        timestamp = msg.can_msg.timestamp
        cycle_time = msg.db_msg.cycle_time
        if cycle_time != 0:
            if (1000 * (current_timestamp - timestamp)) > (timeout * cycle_time):
                alive = 0
            else:
                alive = 1
        elif ((current_timestamp - timestamp)) > timeout:
            alive = 0
        else:
            alive = 1
        return alive

    def get_signal_by_message(self, message_name, signal_name):
        """

        :param message_name: message name in the database
        :param signal_name:  signal name in the database
        :return: the last value on the can bus for the specific signal,
                 if message_name, signal_name not exsit in database or the
                 message not been received yet, will return None.
        """
        try:
            msg = self._message_by_name[message_name]
            value = msg.decoded_msg[signal_name]
        except KeyError:
            return None

        return value

    def send_signal_by_message(self, message_name, signal_dict):
        """

        :param message_name: message name in the database
        :param signal_dict: the signal which you want to update the value.
               this should be a dict type:
               {"sig1":1, "sig2":1}
        :return: 1 means the message send without errors.
                if message_name, signal_dict not valid in database , will return None.
        """
        try:
            msg = self._dbase.get_message_by_name(message_name)
        except KeyError:
            return None
        send_signal_dict = {}
        for sig in msg.signals:
            send_signal_dict[sig.name] = sig.initial if sig.initial != None else 0
        self._send_message_by_name[msg.name] = send_signal_dict

        for sig in signal_dict:
            send_signal_dict[sig] = signal_dict[sig]
        data = msg.encode(send_signal_dict)
        message = can.Message(arbitration_id=msg.frame_id, data=data)
        self._bus.send(message)
        return 1


