import socket

from typing import List
import random
import struct
import time
import math

MAX_RECEIVE_BYTES = 65536
SHORT_PACKET = 3
DATA_FRAME = 5
ACK_FRAME = 6
MAX_STREAMS = 10
ACK_TIMEOUT = 2
MAX_FRAMES_FOR_PACKET = 6
MAX_STREAM_SIZE = 2000
MIN_STREAM_SIZE = 1000


class PacketHeader:
    HEADER_FORMAT = "!BI"  # Format for packing/unpacking the header: unsigned char, unsigned int

    def __init__(self, packet_type: int, packet_number: int):
        self.type = packet_type
        self.number = packet_number

    def serialize(self) -> bytes:
        """
        Serialize the packet header to bytes.

        Returns:
            bytes: Serialized header.
        """
        return struct.pack(self.HEADER_FORMAT, self.type, self.number)

    @classmethod
    def deserialize(cls, data: bytes) -> 'PacketHeader':
        """
        Deserialize bytes to a PacketHeader instance.

        Args:
            data (bytes): Serialized header data.

        Returns:
            PacketHeader: Deserialized PacketHeader instance.
        """
        packet_type, packet_number = struct.unpack(cls.HEADER_FORMAT, data)
        return cls(packet_type, packet_number)


class Frame:
    """
    Represents a frame in a packet.
    """
    FRAME_FORMAT = "!IIQI"  # Format for packing/unpacking the frame: 3 unsigned ints, 1 unsigned long long

    def __init__(self, stream_id: int, frame_type: int, offset: int, length: int):
        self.streamId = stream_id
        self.type = frame_type
        self.offset = offset
        self.length = length

    def update_length(self, length: int):
        """
        Update the length of the frame.

        Args:
            length (int): New length of the frame.
        """
        self.length = length

    def increase_offset(self, offset: int):
        """
        Increase the offset of the frame.

        Args:
            offset (int): Offset to add.
        """
        self.offset += offset

    def serialize(self) -> bytes:
        """
        Serialize the frame to bytes.

        Returns:
            bytes: Serialized frame.
        """
        return struct.pack(self.FRAME_FORMAT, self.streamId, self.type, self.offset, self.length)

    @classmethod
    def deserialize(cls, data: bytes) -> 'Frame':
        """
        Deserialize bytes to a Frame instance.

        Args:
            data (bytes): Serialized frame data.

        Returns:
            Frame: Deserialized Frame instance.
        """
        stream_id, frame_type, offset, length = struct.unpack(cls.FRAME_FORMAT, data)
        return cls(stream_id, frame_type, offset, length)


class MyQUIC:
    """
    A class implementing the MyQUIC protocol for sending and receiving data.
    """
    def __init__(self):
        # Initialize UDP socket for communication
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Calculate sizes of header and frame for later use in serialization/deserialization
        self.headerSize = len(PacketHeader(SHORT_PACKET, 2).serialize())
        self.frameSize = len(Frame(5, DATA_FRAME, 6, 7).serialize())
        self.sentPackets = 0
        self.receivedPackets = 0
        self.stream_bytes_received = {}
        self.streamBytesSent = {}

    def bind(self, server_address):
        self.socket.bind(server_address)

    def send_data(self, address, data_dict: dict[int, bytes]) -> int:
        """
        Send data to the specified address using the MyQUIC protocol.
        """

        stream_sizes = {}  # Dictionary to store sizes of each stream
        frames = []  # List to store all frames
        frames_to_send = []  # List of frames that need to be sent
        streams_durations = {}  # Dictionary to track duration of each stream transmission
        max_stream_time = 0  # Variable to store the longest stream transmission time

        # Create frames for each stream in the input data
        for stream_id, data in data_dict.items():
            # Randomly determine stream size within defined limits
            stream_size = random.randint(MIN_STREAM_SIZE, MAX_STREAM_SIZE)
            stream_sizes[stream_id] = stream_size
            # Create a new frame for this stream
            frame = Frame(stream_id, DATA_FRAME, 0, stream_size)
            frames.append(frame)
            frames_to_send.append(frame)
            # Initialize sent bytes count for this stream if not already present
            if stream_id not in self.streamBytesSent:
                self.streamBytesSent[stream_id] = 0
            streams_durations[stream_id] = 0  # Initialize stream duration

        total_bytes_sent_udp = 0  # Total bytes sent over UDP
        total_bytes_sent_data = 0  # Total data bytes sent (excluding headers and metadata)

        while frames_to_send:
            packet_payload = b""  # Initialize empty payload for this packet
            streams_to_send = []  # List of stream IDs to include in this packet

            # Determine which streams to include in this packet
            if len(frames_to_send) <= MAX_FRAMES_FOR_PACKET:
                streams_to_send = [frame.streamId for frame in frames_to_send]
            else:
                # Randomly select streams if we have more than the maximum allowed per packet
                streams_to_send = random.sample([frame.streamId for frame in frames_to_send], MAX_FRAMES_FOR_PACKET)

            # Prepare data for each selected stream
            for frame in frames_to_send[:]:
                if frame.streamId not in streams_to_send:
                    continue

                # Calculate how many bytes to send for this stream in this packet
                bytes_to_send = min(stream_sizes[frame.streamId], len(data_dict[frame.streamId]) - frame.offset)
                if bytes_to_send == 0:
                    # If no more data to send for this stream, remove it from the list
                    frames_to_send.remove(frame)
                    # Calculate the duration of this stream's transmission
                    streams_durations[frame.streamId] = time.perf_counter() - streams_durations[frame.streamId]
                    max_stream_time = streams_durations[frame.streamId]
                    continue

                # Extract the data for this frame
                stream_data = data_dict[frame.streamId][frame.offset:frame.offset + bytes_to_send]
                frame.update_length(bytes_to_send)
                # Add this frame's data to the packet payload
                packet_payload += frame.serialize() + stream_data

            if not frames_to_send:
                break  # Exit if all frames have been sent

            # Create packet header
            packet_header = PacketHeader(SHORT_PACKET, self.sentPackets)
            self.sentPackets += 1
            packet_to_send = packet_header.serialize() + packet_payload

            # Record start time for the first packet of each stream
            if total_bytes_sent_udp == 0:
                for frame in frames:
                    streams_durations[frame.streamId] = time.perf_counter()

            # Attempt to send the packet and wait for acknowledgment
            total_bytes_sent_udp += self.socket.sendto(packet_to_send, address)

            try:
                # Wait for acknowledgment with a timeout
                self.socket.settimeout(ACK_TIMEOUT)
                received_data, ack_address = self.socket.recvfrom(MAX_RECEIVE_BYTES)
            except socket.timeout:
                print(f"MyQUIC: No response from receiver (address: {address})")
                break

            # Process received acknowledgment
            received_header = PacketHeader.deserialize(received_data[:self.headerSize])
            pointer = self.headerSize

            # Verify if the received ACK matches the sent packet
            if received_header.number != packet_header.number or received_header.type != ACK_FRAME:
                print(f"MyQUIC: No response from receiver (address: {address})")
                break

            # Process each frame in the ACK
            while len(received_data) - pointer >= self.frameSize:
                ack_frame = Frame.deserialize(received_data[pointer:pointer + self.frameSize])
                pointer += self.frameSize

                if ack_frame.type == ACK_FRAME:
                    for sentFrame in frames_to_send:
                        if sentFrame.streamId == ack_frame.streamId:
                            # Update the offset for successfully sent data
                            sentFrame.offset = ack_frame.offset
                            self.streamBytesSent[sentFrame.streamId] += sentFrame.length

                pointer += ack_frame.length

        self.socket.settimeout(None)  # Reset socket timeout

        # Print statistics if significant data was sent
        if frames[0].offset > 50:
            print("\nSTATISTICS:")
            print("\nStreams details:")
            for flow in frames:
                stream_id = flow.streamId
                stream_size = stream_sizes[stream_id]
                total_bytes = flow.offset
                total_bytes_sent_data += total_bytes
                stream_frames = math.ceil(total_bytes // stream_size)
                print(f"Stream: {stream_id+1}, Size: {stream_size} bytes, Sent: {total_bytes} bytes, Sent in {stream_frames} different packets, "
                      f"Pace: {(total_bytes/streams_durations[stream_id]):.2f} B/s, "
                      f"{(stream_frames/streams_durations[stream_id]):.2f} Packets/s")

            print("\nGeneral details:")
            print(f"Data pace: {(total_bytes_sent_data/max_stream_time):.2f} B/s, {(self.sentPackets / max_stream_time):.2f} Packets/s")
            print("\n")

        return total_bytes_sent_data

    def receive_data(self, max_bytes: int = MAX_RECEIVE_BYTES):
        """
        Receive data and send acknowledgment.
        """
        # Receive data
        received_data, sender_address = self.socket.recvfrom(MAX_RECEIVE_BYTES)

        # Deserialize the packet header
        header = PacketHeader.deserialize(received_data[:self.headerSize])
        pointer = self.headerSize
        received_objects = {}
        total_object_bytes = 0

        if header.type == SHORT_PACKET:
            self.receivedPackets += 1
            ack_payload = b""

            # Process each frame in the received packet
            while len(received_data) - pointer >= self.frameSize:
                frame = Frame.deserialize(received_data[pointer:pointer + self.frameSize])
                pointer += self.frameSize

                # Extract data for this frame
                data = received_data[pointer:pointer + frame.length]
                pointer += frame.length
                total_object_bytes += frame.length

                # Initialize byte count for new streams
                if frame.streamId not in self.stream_bytes_received:
                    self.stream_bytes_received[frame.streamId] = 0

                # Check if the received data is in the expected order
                if frame.offset == self.stream_bytes_received[frame.streamId]:
                    frame.increase_offset(frame.length)
                    self.stream_bytes_received[frame.streamId] += frame.length
                else:
                    # If out of order, set the offset to the last known good position
                    frame.offset = self.stream_bytes_received[frame.streamId]

                # Prepare ACK frame
                frame.length = 0
                frame.type = ACK_FRAME
                ack_payload += frame.serialize()

                # Store received data if within size limit
                if total_object_bytes <= max_bytes:
                    received_objects[frame.streamId] = data

            # Send acknowledgment back to the sender
            ack_header = PacketHeader(ACK_FRAME, header.number)
            self.sentPackets += 1
            self.socket.sendto(ack_header.serialize() + ack_payload, sender_address)

        return sender_address, received_objects

    def close(self):
        self.socket.close()
