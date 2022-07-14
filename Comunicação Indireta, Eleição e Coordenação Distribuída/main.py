import sys, os
from node import Node

if __name__ == "__main__":
    try:
        Node(1000).join()
    except KeyboardInterrupt:
        print("Interrupted!")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
