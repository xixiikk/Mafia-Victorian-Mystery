class Logger:
    def __init__(self, name, game_dir):
        self.name = name
        self.game_dir = game_dir

    def log(self, tag, message):
        print(f"[{tag}] {message}")