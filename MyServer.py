import random
import MY_QUIC

def createRandomObject(size_bytes):
    """
    Create a random byte object of specified size.

    Args:
        size_bytes (int): Size of the byte object in bytes.

    Returns:
        bytes: A byte object filled with random bytes.
    """
    return bytes(random.getrandbits(8) for _ in range(size_bytes))

def main():
    """
    Main function to set up the server, generate random objects, handle client requests,
    and send back the requested data.
    """
    numOfObjects = 10  # Number of random objects to create
    minSizeBytes = 1 * 1024 * 1024  # Minimum size of each object (1 MB)
    maxSizeBytes = 2 * 1024 * 1024  # Maximum size of each object (2 MB)

    print("Creating objects...")
    # Generate random sizes for the objects and create the objects
    objectSizes = [random.randint(minSizeBytes, maxSizeBytes) for _ in range(numOfObjects)]
    # Create random objects of various sizes using the createRandomObject function
    randomObjects = [createRandomObject(size) for size in objectSizes]
    print("Objects creation complete!")

    print("Starting server...")
    server = MY_QUIC.MY_QUIC()  # Initialize the MY_QUIC server
    serverAddress = ('localhost', 9999)  # Server address and port
    server.bind(serverAddress)  # Bind the server to the address
    print("Server is ready!")

    while True:
        print("Waiting for client connections...")
        # Wait for data from clients; receive the client address and data
        clientAddress, data = server.receiveData(65536)  # Buffer size of 65536 bytes

        requestStreamId = 18  # Define the stream ID used for requests
        if requestStreamId in data:
            print("Client request details:")
            # Decode the received request data
            requestStr = data[requestStreamId].decode()
            # Split the request into stream-object pairs
            streamObjectPairs = requestStr.split()

            responseData = {}
            totalRequestSize = 0

            # Process each request pair and prepare the response data
            for pair in streamObjectPairs:
                # Extract stream ID and object index from the pair
                streamId, objectIndex = map(int, pair.split(':'))
                # Retrieve the object based on the index and assign it to the stream ID
                responseData[streamId] = randomObjects[objectIndex]
                # Update the total size of the response
                totalRequestSize += len(responseData[streamId])
                print(f"Stream: {streamId}, Object: {objectIndex}, Actual size: {objectSizes[objectIndex]} bytes")

            print(f"Total response size: {totalRequestSize} bytes")
            print("Sending response data...\n")
            # Send the requested objects back to the client
            server.sendData(clientAddress, responseData)

        print("Sending termination message")
        # Send a termination message to the client
        server.sendData(clientAddress, {81: b"fin"})

        # Ask the user if they want to receive another request
        if input("Receive another request?\n(1 - no, 2 - yes): ") != "2":
            break  # Exit the loop if the user does not want to process more requests

    server.close()
    print("Server shutdown!")

if __name__ == '__main__':
    main()