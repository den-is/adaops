import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)


class CardanoCLI:
    def __init__(self, cardano_binary, **kwargs):
        binary_path = shutil.which(cardano_binary)

        if binary_path is None:
            raise ValueError(f"Binary '{cardano_binary}' is not found in the $PATH.")

        if not os.access(binary_path, os.X_OK):
            raise ValueError(f"Binary '{cardano_binary}' is not executable.")

        self.cardano_binary = cardano_binary
        self.binary_path = binary_path
        self.init_kwargs = kwargs

    def run(self, *args, **kwargs):
        all_kwargs = {**self.init_kwargs, **kwargs}

        command = [self.cardano_binary] + [str(arg) for arg in args]

        command_str = " ".join([str(arg) for arg in command])

        logger.debug(
            "Command to be executed: '%s' with Popen kwargs: '%s'", command_str, all_kwargs
        )

        proc = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **all_kwargs
        )

        try:
            stdout, stderr = proc.communicate()
        # TODO: for now it is useless since we are not passing timeout to communicate()
        # TODO: maybe wrap whole subprocess.Poppen in try-except
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()

        returncode = proc.returncode

        return {
            "stdout": stdout.decode("utf-8"),
            "stderr": stderr.decode("utf-8"),
            "rc": returncode,
            "cmd": command_str,
            "popen_args": all_kwargs,
        }
