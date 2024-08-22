import random
import MyQUIC


def create_random_files(size_bytes):
    return bytes(random.getrandbits(8) for _ in range(size_bytes))


def main():
    """
    Main function to set up the server, generate random files, handle client requests,
    and send back the requested data.
    """
    num_of_files = 10
    # Min and max size of each file
    min_size_bytes = 1 * 1024 * 1024  # 1 MB
    max_size_bytes = 2 * 1024 * 1024  # 2 MB

    print("Creating files...")
    # Generate random sizes for the files and create them
    file_sizes = [random.randint(min_size_bytes, max_size_bytes) for _ in range(num_of_files)]
    random_files = [create_random_files(size) for size in file_sizes]
    print("Files creation complete!")

    print("Starting server...")
    server = MyQUIC.MyQUIC()
    server_address = ('localhost', 1212)  # Server address and port
    server.bind(server_address)  # Bind the server to the address
    print("Server is ready!")

    while True:
        print("Waiting for client connections...")
        client_address, data = server.receive_data(65536)  # Buffer size of 65536 bytes

        request_stream_id = 18  # Define the stream ID used for requests, format
        if request_stream_id in data:
            print("Client request details:")
            request_str = data[request_stream_id].decode()
            stream_file_pairs = request_str.split()      # Split the request into stream-file pairs

            response_data = {}
            total_request_size = 0

            # Process each request pair and prepare the response data
            for pair in stream_file_pairs:
                stream_id, file_index = map(int, pair.split('->'))     # Splitting the string "stream_id->file_index"
                response_data[stream_id] = random_files[file_index]
                total_request_size += len(response_data[stream_id])         # Update the total size of the response
                print(f"Stream: {stream_id+1}, file: {file_index+1}, Actual size: {file_sizes[file_index]} bytes")

            print(f"Total response size: {total_request_size} bytes")
            print("Sending response data...\n")
            server.send_data(client_address, response_data)

        print("Sending finish message")
        server.send_data(client_address, {81: b"fin"})
        break

    server.close()
    print("Server shutdown!")


if __name__ == '__main__':
    main()