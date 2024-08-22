import MyQUIC
import random


def main():
    """
    Main function generate requests and interact with the server.
    """
    num_files = 0
    # get input from the user
    while True:
        try:
            # Get input from the user
            num_files = int(input("Please enter the number of files (1-10): "))

            # Check if the input is within the desired range
            if 1 <= num_files <= 10:
                print(f"You entered: {num_files}")
                break  # Exit the loop since the input is valid
            else:
                print("The number must be between 1 and 10. Please try again.")

        except ValueError:
            print("That's not a valid integer! Please enter a number between 1 and 10.")

    # Generate random stream-file pairs
    stream_number = list(range(10))  # A list of stream numbers from 0 to 9
    file_number = list(range(10))    # A list of file numbers
    random.shuffle(stream_number)
    random.shuffle(file_number)
    # Create pairs of (stream number, file number) for the number of files requested
    pairs = [(stream_number[i], file_number[i]) for i in range(num_files)]
    # Create a request string in the format "stream:file stream:file ..."
    request_str = " ".join([f"{pair[0]}->{pair[1]}" for pair in pairs])
    # Create a similar string but with stream_id and file_index incremented by 1 for display purposes
    print_request = " ".join([f"{pair[0]+1}->{pair[1]+1}" for pair in pairs])

    # Set up MY_QUIC client
    print("Client starting...")
    client = MyQUIC.MyQUIC()
    server_address = ('localhost', 1212)  # Server address and port

    # Send request to the server
    request_stream_id = 18  # Dedicated stream ID for sending requests
    my_request = {request_stream_id: request_str.encode()}

    print(f"Sending request: {print_request}")
    client.send_data(server_address, my_request)

    # Prepare to receive response data
    response_data = {int(pair[0]): b"" for pair in pairs}  # Initialize empty byte strings for each requested stream
    response_data[81] = b""  # Stream 81 is used for server acknowledgement
    print("Waiting for data...\n")
    packets_received = 0

    # Receive and accumulate data from the server
    print("Receiving data...")
    while response_data[81] != b"fin":
        _, response = client.receive_data(65536)
        packets_received += 1
        for streamId, data in response.items():
            response_data[streamId] += data  # Accumulate data for each stream

    print("Data reception complete!\n")
    print(f"Total packets received: {packets_received}")

    # Print the received data details
    del response_data[81]
    for i, (streamId, data) in enumerate(response_data.items()):
        file_number = pairs[i][1]  # Get the corresponding file number for this stream
        print(f"Stream: {streamId+1}, File number: {file_number+1}, File size: {len(data)} bytes")

    client.close()
    print("\nClient shutdown!")


if __name__ == '__main__':
    main()