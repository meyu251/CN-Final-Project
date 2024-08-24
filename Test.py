import threading
import unittest
from time import sleep

from MyQUIC import MyQUIC

TEST_COUNTER = 4

def myquic_echo_server():
    """
    This function creates a threaded server that receives data from the client and echoes it back.
    The server will process data for TEST_COUNTER times.
    """
    server_sock = MyQUIC()
    server_sock.bind(('localhost', 1212))

    for i in range(TEST_COUNTER):
        addr, data = server_sock.receive_data(65536)
        if i == TEST_COUNTER - 1:  # In the last test, we need two packets due to the 6-frame limitation per packet
            addr, data_second = server_sock.receive_data(65536)
            first_key = next(iter(data_second))
            data[first_key] = data_second[first_key]
        server_sock.send_data(addr, data)

    server_sock.close()

class TestMyQUIC(unittest.TestCase):
    """
    This class contains tests for the MyQUIC class.
    It includes tests for sending and receiving data with various stream counts,
    as well as handling empty data transmission.
    """

    @classmethod
    def setUpClass(cls):  # This method is called before tests in an individual class are run
        cls.server_thread = threading.Thread(target=myquic_echo_server, daemon=True)  # Creating a thread for the server
        cls.server_thread.start()

    def setUp(self):
        self.client_sock = MyQUIC()  # Creating an instance of MyQUIC that will represent the client
        self.server_address = ('localhost', 1212)

    def tearDown(self):
        self.client_sock.close()

    def test_send_and_receive1(self):
        # Test sending and receiving non-empty data in 1 stream
        data_to_send = {1: "Hi there".encode()}
        self.client_sock.send_data(self.server_address, data_to_send)
        received_address, received_data = self.client_sock.receive_data(65536)
        self.assertEqual(received_address, ('127.0.0.1', 1212))
        self.assertEqual(received_data, data_to_send)

    def test_send_and_receive2(self):
        # Test sending and receiving non-empty data in 2 streams
        data_to_send = {1: "Hi there".encode(), 2: "Hello".encode()}
        self.client_sock.send_data(self.server_address, data_to_send)
        received_address, received_data = self.client_sock.receive_data(65536)
        self.assertEqual(received_address, ('127.0.0.1', 1212))
        self.assertEqual(received_data, data_to_send)

    def x_test_send_and_receive8(self):
        # Test sending and receiving non-empty data in 8 streams
        data_to_send = {i: f"Hi there {i}".encode() for i in range(1, 9)}
        self.client_sock.send_data(self.server_address, data_to_send)
        received_address, received_data = self.client_sock.receive_data(65536)
        received_address, received_data_second = self.client_sock.receive_data(65536)
        first_key = next(iter(received_data_second))
        received_data[first_key] = received_data_second[first_key]
        self.assertEqual(received_address, ('127.0.0.1', 1212))
        self.assertEqual(received_data, data_to_send)

    def test_send_empty(self):
        # Test sending and receiving empty data
        data_to_send = {1: b''}
        bytes_sent = self.client_sock.send_data(self.server_address, data_to_send)
        self.assertEqual(bytes_sent, 0)

if __name__ == '__main__':
    unittest.main()