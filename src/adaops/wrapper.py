import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)


class CardanoCLI:
    def __init__(self, cardano_binary, cardano_era, use_legacy_commands, **kwargs):
        binary_path = shutil.which(cardano_binary)

        if binary_path is None:
            raise ValueError(f"Binary '{cardano_binary}' is not found in the $PATH.")

        if not os.access(binary_path, os.X_OK):
            raise ValueError(f"Binary '{cardano_binary}' is not executable.")

        self.cardano_binary = cardano_binary
        self.binary_path = binary_path
        self.cardano_era = cardano_era
        self.use_legacy_commands = use_legacy_commands
        self.init_kwargs = kwargs

    def run(self, *args, cmd_group=None, **kwargs):
        all_kwargs = {**self.init_kwargs, **kwargs}

        command_group = []
        # if requesting legacy commands or era is not set, use legacy commands
        # commands under legacy group require era argument --<era-name>-era
        # at the moment of writing, and node v8.9.4 cli v8.20.3.0 legacy group commands
        # exist in the top level of the cli, so we explicitly set the group to "legacy"
        # if cardano_era not provided, that means we are using legacy commands
        # (at least trying to use top-level legacy commands)
        if cmd_group:
            # TODO: check if the command group is valid
            # for example used to set `debug` command group
            command_group = [cmd_group]
        elif self.use_legacy_commands or not self.cardano_era:
            command_group = ["legacy"]
        else:
            command_group = [self.cardano_era.lower()]

        command = [self.cardano_binary] + command_group + [str(arg) for arg in args]

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
            "stdout": stdout,
            "stderr": stderr,
            "rc": returncode,
            "cmd": command_str,
            "popen_args": all_kwargs,
        }
