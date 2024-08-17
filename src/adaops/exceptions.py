class AdaopsException(Exception):
    """adaops base exception class"""


class NodeDown(AdaopsException):
    """Cardano-node is OFFLINE or the service LOADING is in progress"""

    def __init__(
        self,
        msg="cardano-node service is DOWN or LOADING is in progress. cardano-node socket is not responding.",  # noqa
    ):
        super().__init__(msg)


class ObjectMissingKey(AdaopsException):
    """Queried JSON is missing key or has bad structure"""

    def __init__(
        self,
        msg="Requested key is missing in the object, or object has bad structure.",
        obj=None,
    ):
        super().__init__(msg)
        self.msg = msg
        self.obj = obj

    def __str__(self):
        return f"{self.msg} Bad object: {self.obj}"


class BadCmd(AdaopsException):
    """Bad CLI command and/or its arguments"""

    def __init__(
        self,
        msg="Bad CLI command or bad arguments supplied to a command.",
        cmd=None,
    ):
        super().__init__(msg)
        self.msg = msg
        self.cmd = cmd

    def __str__(self):
        return f"{self.msg} Bad command: {self.cmd}"
