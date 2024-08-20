import random
import MY_QUIC

def createRandomObject(size_bytes):
    return bytes(random.getrandbits(8) for _ in range(size_bytes))

def main():
    """
    Main function to set up the server, generate random objects, handle client requests,
    and send back the requested data.
    """
    numOfObjects = 10
    # Min and max size of each object
    minSizeBytes = 1 * 1024 * 1024  # 1 MB
    maxSizeBytes = 2 * 1024 * 1024  # 2 MB

    print("Creating objects...")
    # Generate random sizes for the objects and create them
    objectSizes = [random.randint(minSizeBytes, maxSizeBytes) for _ in range(numOfObjects)]
    randomObjects = [createRandomObject(size) for size in objectSizes]
    print("Objects creation complete!")

    print("Starting server...")
    server = MY_QUIC.MY_QUIC()
    serverAddress = ('localhost', 1212)  # Server address and port
    server.bind(serverAddress)  # Bind the server to the address
    print("Server is ready!")

    while True:
        print("Waiting for client connections...")
        clientAddress, data = server.receiveData(65536)  # Buffer size of 65536 bytes

        requestStreamId = 18  # Define the stream ID used for requests
        if requestStreamId in data:
            print("Client request details:")
            requestStr = data[requestStreamId].decode()
            streamObjectPairs = requestStr.split()      # Split the request into stream-object pairs

            responseData = {}
            totalRequestSize = 0

            # Process each request pair and prepare the response data
            for pair in streamObjectPairs:
                streamId, objectIndex = map(int, pair.split(':'))
                responseData[streamId] = randomObjects[objectIndex]
                totalRequestSize += len(responseData[streamId])         # Update the total size of the response
                print(f"Stream: {streamId}, Object: {objectIndex}, Actual size: {objectSizes[objectIndex]} bytes")

            print(f"Total response size: {totalRequestSize} bytes")
            print("Sending response data...\n")
            server.sendData(clientAddress, responseData)

        print("Sending finish message")
        server.sendData(clientAddress, {81: b"fin"})

        break

    server.close()
    print("Server shutdown!")

if __name__ == '__main__':
    main()