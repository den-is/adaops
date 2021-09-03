# Examples
Almost every method in that library accepts `cwd` argument.

That makes library method to execute, looks for files or output final results in directory passed to `cwd` argument.

Also many examples use top-level `CWD` variable, that helps to build paths based on `CWD` and pass them to `cwd` argument. Of course `cwd` argument accepts arbitrary valid POSIX path.

- To generate [KES keys](https://developers.cardano.org/docs/operate-a-stake-pool/cardano-key-pairs/#kes-hot-keys) and generate Operations Node Certificate, you can use this [snippet](rotate_kes_op_cert.py)
