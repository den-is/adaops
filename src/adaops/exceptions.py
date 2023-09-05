class NodeOffline(Exception):
    """Cardano-node is OFFLINE or the service LOADING is in progress"""

    def __init__(self, message):
        super().__init__(message)

    def __str__(self):
        return str(self.message)
