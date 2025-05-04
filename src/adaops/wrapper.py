import logging
import os
import shlex
import shutil
import subprocess

logger = logging.getLogger(__name__)


class CardanoCLI:
    def __init__(self, cardano_binary, cardano_era, **kwargs):
        """CardanoCLI wrapper for cardano-cli

        Args:
            cardano_binary: path to the cardano binary
            cardano_era: cardano era (e.g. 'conway', 'latest', etc.) should be a command group in the cardano-cli

        Raises:
            ValueError: Binary '{cardano_binary}' is not found in the $PATH
            ValueError: Binary '{cardano_binary}' is not executable
        """

        binary_path = shutil.which(cardano_binary)

        if binary_path is None:
            raise ValueError(f"Binary '{cardano_binary}' is not found in the $PATH")

        if not os.access(binary_path, os.X_OK):
            raise ValueError(f"Binary '{cardano_binary}' is not executable")

        self.cardano_binary = cardano_binary
        self.binary_path = binary_path
        self.cardano_era = cardano_era
        self.init_kwargs = kwargs

    def run(self, *args, cmd_group=None, **kwargs):
        all_kwargs = {**self.init_kwargs, **kwargs}

        command_group = ""

        if cmd_group:
            # TODO: check if the command group is valid
            # for example used to set `debug` command group
            command_group = cmd_group
        else:
            command_group = self.cardano_era.lower()

        command = [self.cardano_binary, command_group] + [str(arg) for arg in args]

        command_str = shlex.join(command)

        logger.debug(
            "Command to be executed: '%s' with Popen kwargs: '%s'", command_str, all_kwargs
        )

        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            **all_kwargs,
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
            "stdout": stdout,
            "stderr": stderr,
            "rc": returncode,
            "cmd": command_str,
            "popen_args": all_kwargs,
        }
