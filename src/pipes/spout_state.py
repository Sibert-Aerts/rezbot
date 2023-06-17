
class SpoutState:

    # Flags etc.
    encountered_print: bool = False
    suppressed_print: bool = False

    # Data
    print_values: list[list[str]]
    callbacks: list[tuple]

    def __init__(self, print_values=None, callbacks=None):
        self.print_values = print_values if print_values is not None else []
        self.callbacks = callbacks if callbacks is not None else []

    def extend(self, other: 'SpoutState', extend_print=False):
        self.print_values.extend(other.print_values)
        self.callbacks.extend(other.callbacks)
