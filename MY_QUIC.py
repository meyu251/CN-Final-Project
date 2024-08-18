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
MAX_RETRIES = 4
MAX_FRAMES_FOR_PACKET = 7
MAX_STREAM_SIZE = 2000
MIN_STREAM_SIZE = 1000

class PacketHeader:
    HEADER_FORMAT = "!BI"  # Format for packing/unpacking the header: unsigned char, unsigned int

    def __init__(self, packetType: int, packetNumber: int):
        self.type = packetType
        self.number = packetNumber

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
        packetType, packetNumber = struct.unpack(cls.HEADER_FORMAT, data)
        return cls(packetType, packetNumber)


class Frame:
    """
    Represents a frame in a packet.
    """
    FRAME_FORMAT = "!IIQI"  # Format for packing/unpacking the frame: 3 unsigned ints, 1 unsigned long long

    def __init__(self, streamId: int, frameType: int, offset: int, length: int):
        self.streamId = streamId
        self.type = frameType
        self.offset = offset
        self.length = length

    def updateLength(self, length: int):
        """
        Update the length of the frame.

        Args:
            length (int): New length of the frame.
        """
        self.length = length

    def increaseOffset(self, offset: int):
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
        streamId, frameType, offset, length = struct.unpack(cls.FRAME_FORMAT, data)
        return cls(streamId, frameType, offset, length)


class Connection:
    """
    Represents a connection with a client.
    """
    def __init__(self, address, connectionId):
        self.address = address
        self.id = connectionId
        self.sentPackets = 0
        self.receivedPackets = 0
        self.streamBytesReceived = {}
        self.streamBytesSent = {}


class MY_QUIC:
    """
    A class implementing the MY_QUIC protocol for sending and receiving data.
    """
    def __init__(self):
        # Initialize UDP socket for communication
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.connections = []  # List to store all active connections
        # Calculate sizes of header and frame for later use in serialization/deserialization
        self.headerSize = len(PacketHeader(SHORT_PACKET, 2).serialize())
        self.frameSize = len(Frame(5, DATA_FRAME, 6, 7).serialize())

    def bind(self, serverAddress):
        """
        Bind the server to the specified address.
        """
        self.socket.bind(serverAddress)

    def getOrCreateConnection(self, address) -> Connection:
        """
        Retrieve an existing connection or create a new one for the given address.
        """
        # Check if a connection already exists for this address
        for conn in self.connections:
            if conn.address == address:
                return conn
        # If no existing connection, create a new one
        newConn = Connection(address, len(self.connections))
        self.connections.append(newConn)
        return newConn

    def sendData(self, address, dataDict: dict[int, bytes]) -> int:
        """
        Send data to the specified address using the MY_QUIC protocol.
        """
        connection = self.getOrCreateConnection(address)

        streamSizes = {}  # Dictionary to store sizes of each stream
        frames = []  # List to store all frames
        framesToSend = []  # List of frames that need to be sent
        streamsDurations = {}  # Dictionary to track duration of each stream transmission
        maxStreamTime = 0  # Variable to store the longest stream transmission time

        # Create frames for each stream in the input data
        for streamId, data in dataDict.items():
            # Randomly determine stream size within defined limits
            streamSize = random.randint(MIN_STREAM_SIZE, MAX_STREAM_SIZE)
            streamSizes[streamId] = streamSize
            # Create a new frame for this stream
            frame = Frame(streamId, DATA_FRAME, 0, streamSize)
            frames.append(frame)
            framesToSend.append(frame)
            # Initialize sent bytes count for this stream if not already present
            if streamId not in connection.streamBytesSent:
                connection.streamBytesSent[streamId] = 0
            streamsDurations[streamId] = 0  # Initialize stream duration

        totalBytesSentUdp = 0  # Total bytes sent over UDP
        totalBytesSentData = 0  # Total data bytes sent (excluding headers and metadata)

        while framesToSend:
            packetPayload = b""  # Initialize empty payload for this packet
            streamsToSend = []  # List of stream IDs to include in this packet

            # Determine which streams to include in this packet
            if len(framesToSend) <= MAX_FRAMES_FOR_PACKET:
                streamsToSend = [frame.streamId for frame in framesToSend]
            else:
                # Randomly select streams if we have more than the maximum allowed per packet
                streamsToSend = random.sample([frame.streamId for frame in framesToSend], MAX_FRAMES_FOR_PACKET)

            # Prepare data for each selected stream
            for frame in framesToSend[:]:
                if frame.streamId not in streamsToSend:
                    continue

                # Calculate how many bytes to send for this stream in this packet
                bytesToSend = min(streamSizes[frame.streamId], len(dataDict[frame.streamId]) - frame.offset)
                if bytesToSend == 0:
                    # If no more data to send for this stream, remove it from the list
                    framesToSend.remove(frame)
                    # Calculate the duration of this stream's transmission
                    streamsDurations[frame.streamId] = time.perf_counter() - streamsDurations[frame.streamId]
                    maxStreamTime = streamsDurations[frame.streamId]
                    continue

                # Extract the data for this frame
                streamData = dataDict[frame.streamId][frame.offset:frame.offset + bytesToSend]
                frame.updateLength(bytesToSend)
                # Add this frame's data to the packet payload
                packetPayload += frame.serialize() + streamData

            if not framesToSend:
                break  # Exit if all frames have been sent

            # Create packet header
            packetHeader = PacketHeader(SHORT_PACKET, connection.sentPackets)
            connection.sentPackets += 1
            packetToSend = packetHeader.serialize() + packetPayload

            # Record start time for the first packet of each stream
            if totalBytesSentUdp == 0:
                for frame in frames:
                    streamsDurations[frame.streamId] = time.perf_counter()

            # Attempt to send the packet and wait for acknowledgment
            for attempt in range(MAX_RETRIES):
                totalBytesSentUdp += self.socket.sendto(packetToSend, address)

                try:
                    # Wait for acknowledgment with a timeout
                    self.socket.settimeout(ACK_TIMEOUT)
                    receivedData, ackAddress = self.socket.recvfrom(MAX_RECEIVE_BYTES)
                except socket.timeout:
                    continue  # Retry if timeout occurs

                # Process received acknowledgment
                receivedHeader = PacketHeader.deserialize(receivedData[:self.headerSize])
                pointer = self.headerSize

                # Verify if the received ACK matches the sent packet
                if receivedHeader.number != packetHeader.number or receivedHeader.type != ACK_FRAME:
                    continue  # Retry if ACK doesn't match

                # Process each frame in the ACK
                while len(receivedData) - pointer >= self.frameSize:
                    ackFrame = Frame.deserialize(receivedData[pointer:pointer + self.frameSize])
                    pointer += self.frameSize

                    if ackFrame.type == ACK_FRAME:
                        for sentFrame in framesToSend:
                            if sentFrame.streamId == ackFrame.streamId:
                                # Update the offset for successfully sent data
                                sentFrame.offset = ackFrame.offset
                                connection.streamBytesSent[sentFrame.streamId] += sentFrame.length

                    pointer += ackFrame.length

                break  # Exit retry loop if ACK received successfully
            else:
                # If max retries reached without success
                print(f"MY_QUIC: No response from receiver (address: {address})")
                break

        self.socket.settimeout(None)  # Reset socket timeout

        # Print statistics if significant data was sent
        if frames[0].offset > 50:
            print("\n-------------------------------------- STATES --------------------------------------")
            print("\n(a)+(b)+(c): Streams info")
            for flow in frames:
                streamId = flow.streamId
                streamSize = streamSizes[streamId]
                totalBytes = flow.offset
                totalBytesSentData += totalBytes
                streamFrames = math.ceil(totalBytes // streamSize)
                print(f"Stream: {streamId}, Size: {streamSize} bytes, Sent: {totalBytes} bytes, "
                      f"Pace: {(totalBytes/streamsDurations[streamId]):.2f} B/s, "
                      f"{(streamFrames/streamsDurations[streamId]):.2f} Packets/s")

            print("\n(d)+(e): Connection info:")
            print(f"Data pace: {(totalBytesSentData/maxStreamTime):.2f} B/s, {(connection.sentPackets / maxStreamTime):.2f} Packets/s")
            print("\n------------------------------------------------------------------------------------\n")

        return totalBytesSentData

    def receiveData(self, max_bytes: int = MAX_RECEIVE_BYTES):
        """
        Receive data from a client and send acknowledgment.
        """
        # Receive data from any client
        received_data, sender_address = self.socket.recvfrom(MAX_RECEIVE_BYTES)
        connection = self.getOrCreateConnection(sender_address)

        # Deserialize the packet header
        header = PacketHeader.deserialize(received_data[:self.headerSize])
        pointer = self.headerSize
        received_objects = {}
        total_object_bytes = 0

        if header.type == SHORT_PACKET:
            connection.receivedPackets += 1
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
                if frame.streamId not in connection.streamBytesReceived:
                    connection.streamBytesReceived[frame.streamId] = 0

                # Check if the received data is in the expected order
                if frame.offset == connection.streamBytesReceived[frame.streamId]:
                    frame.increaseOffset(frame.length)
                    connection.streamBytesReceived[frame.streamId] += frame.length
                else:
                    # If out of order, set the offset to the last known good position
                    frame.offset = connection.streamBytesReceived[frame.streamId]

                # Prepare ACK frame
                frame.length = 0
                frame.type = ACK_FRAME
                ack_payload += frame.serialize()

                # Store received data if within size limit
                if total_object_bytes <= max_bytes:
                    received_objects[frame.streamId] = data

            # Send acknowledgment back to the sender
            ack_header = PacketHeader(ACK_FRAME, header.number)
            connection.sentPackets += 1
            self.socket.sendto(ack_header.serialize() + ack_payload, sender_address)

        return sender_address, received_objects

    def close(self):
        self.socket.close()