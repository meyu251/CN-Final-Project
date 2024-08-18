import MY_QUIC
import sys
import random

def main():
    """
    Main function to handle command-line arguments, generate requests, and interact with the server.
    """
    # Handle command-line arguments
    if len(sys.argv) != 2 or not sys.argv[1].isdigit() or int(sys.argv[1]) > 10:
        print("ERROR: Please enter a number between 1-10 (for the number of files to send)")
        return
    numFiles = int(sys.argv[1])  # Number of file requests to send

    # Generate random stream-object pairs
    streamNumber = list(range(10))  # Create a list of stream numbers from 0 to 9
    fileNumber = list(range(10))    # Create a list of file numbers from 0 to 9
    random.shuffle(streamNumber)    # Shuffle the stream numbers
    random.shuffle(fileNumber)      # Shuffle the file numbers
    # Create pairs of (stream number, file number) for the number of files requested
    pairs = [(streamNumber[i], fileNumber[i]) for i in range(numFiles)]
    # Create a request string in the format "stream:file stream:file ..."
    requestStr = " ".join([f"{pair[0]}:{pair[1]}" for pair in pairs])

    # Set up MY_QUIC client
    print("Client starting...")
    client = MY_QUIC.MY_QUIC()  # Initialize the MY_QUIC client
    serverAddress = ('localhost', 9999)  # Server address and port

    # Send request to the server
    requestStreamId = 18  # Dedicated stream ID for sending requests
    myRequest = {requestStreamId: requestStr.encode()}  # Encode the request string
    print(f"Sending request: {requestStr}")
    client.sendData(serverAddress, myRequest)  # Send the request to the server

    # Prepare to receive response data
    responseData = {int(pair[0]): b"" for pair in pairs}  # Initialize empty byte strings for each requested stream
    responseData[81] = b""  # Stream 81 is used for server acknowledgement
    print("Waiting for data...\n")
    packetsReceived = 0  # Counter for received packets

    # Receive and accumulate data from the server
    print("Receiving data...")
    while responseData[81] != b"fin":  # Continue receiving until the server sends the "fin" message
        _, response = client.receiveData(65536)  # Receive data (max 65536 bytes per packet)
        packetsReceived += 1
        for streamId, data in response.items():
            responseData[streamId] += data  # Accumulate data for each stream

    print("Data reception complete!\n")
    print(f"Total packets received: {packetsReceived}")

    # Print the received data details
    del responseData[81]  # Remove the acknowledgment stream from the results
    for i, (streamId, data) in enumerate(responseData.items()):
        objectNumber = pairs[i][1]  # Get the corresponding object number for this stream
        print(f"Stream: {streamId}, Object number: {objectNumber}, Object size: {len(data)} bytes")

    client.close()
    print("\nClient shutdown!")

if __name__ == '__main__':
    main()